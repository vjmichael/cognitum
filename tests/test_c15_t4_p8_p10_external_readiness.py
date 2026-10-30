"""Synthetic only: contract regressions and hostile inputs, no real issuer/data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p5_p7 import canonical, sha
from cognitum.spatial_functional_material_p8_p10 import (
    P8_DOMAIN,P9_DOMAIN,HostHighwater,PolicySnapshot,policy_snapshot,
    advance_policy_highwater,evaluate_p9,evaluate_p10,
)
from cognitum.proto import spatial_functional_material_p8_p10_pb2 as w
from tests.test_c15_t4_p5_p7_assurance import create, signed


def pub(k):
    return k.public_key().public_bytes(serialization.Encoding.Raw,
                                       serialization.PublicFormat.Raw)


def make_policy(prior=None, keys=None, root=None, generation=1, modifications=None):
    root=root or Ed25519PrivateKey.generate()
    keys=keys or create()[2]
    extra=Ed25519PrivateKey.generate()
    keys=dict(keys)
    keys.setdefault('notary',extra)
    roles={'publisher':'publisher','lock':'plan_attestor',
           'review_a':'reviewer','review_b':'reviewer','notary':'time_notary'}
    entries=[dict(key_id=k,role=roles[k],public_key_hex=pub(v).hex(),
                  valid_from_ms=1789999998000,valid_until_ms=1790001000000,
                  revoked=False) for k,v in sorted(keys.items())]
    body=dict(schema_version=1,policy_id='research-study-alpha',
              generation=generation,previous_sha256=prior or '0'*64,keys=entries)
    if modifications: modifications(body)
    envelope=w.T4TrustPolicyEnvelope(schema_version=1,research_only=True,
                                      root_key_id='fixture_root')
    envelope.canonical_policy_json=canonical(body)
    envelope.ed25519_signature=root.sign(P8_DOMAIN+envelope.canonical_policy_json)
    return envelope,{'fixture_root':pub(root)},root,keys


def make_p9():
    p7,_,keys=create(n=2)
    envelope,pinned,root,k=make_policy(keys=keys)
    snap=policy_snapshot(envelope,pinned)
    req=w.T4P9TimeAnchorRequest(schema_version=1,research_only=True)
    req.p7.CopyFrom(p7)
    req.notary_statement.key_id='notary'
    signed(req.notary_statement,k['notary'],P9_DOMAIN,dict(
        schema_version=1,study_id=p7.p6.p5.p4.p3_audit.study_id,
        p6_sha256=sha(p7.p6.SerializeToString(deterministic=True)),
        issued_at_ms=1790000000500,notary_sequence=1))
    return req,snap,k


def make_dataset():
    raw=('specimen_id,group_id,partition,observed_class,measured_clearance_m,calibration_id\n'
         's1,g1,calibration,satisfies,1.5,cal1\n'
         's2,g2,holdout,violates,-0.25,cal1\n').encode()
    cal=b'fixture calibration bytes - not instrument proof'
    m=dict(schema_version=1,dataset_id='fixture_data',study_id='study_alpha',
           raw_csv_sha256=sha(raw),declared_source_uri='fixture:local',
           declared_license_id='synthetic_fixture',units='m',
           partition_policy='group_isolated',calibration_sha256_by_id={'cal1':sha(cal)},
           intended_use='research_only')
    req=w.T4P10DatasetIntakeRequest(schema_version=1,research_only=True,
                                    raw_csv=raw,manifest_json=canonical(m))
    req.calibration_documents.add(ref_id='cal1',content=cal)
    return req,m


class P8TrustPolicyTests(unittest.TestCase):
    def bad(self,env,roots,code):
        with self.assertRaisesRegex(T4Rejected,code):policy_snapshot(env,roots)

    def test_fixture_policy_and_roles(self):
        env,roots,_,_=make_policy()
        snap=policy_snapshot(env,roots)
        self.assertEqual(len(snap.signers),5)
        self.assertEqual(snap.signers['notary'].role,'time_notary')

    def test_root_unpinned(self):
        env,roots,_,_=make_policy()
        self.bad(env,{},'UNPINNED_POLICY_ROOT')

    def test_root_sig_tamper(self):
        env,roots,_,_=make_policy()
        env.ed25519_signature=b'\x00'*64
        self.bad(env,roots,'INVALID_ROOT_SIGNATURE')

    def test_policy_mutation(self):
        env,roots,_,_=make_policy()
        env.canonical_policy_json=env.canonical_policy_json.replace(b'research-study-alpha',b'research-study-betaa')
        self.bad(env,roots,'INVALID_ROOT_SIGNATURE')

    def test_duplicate_key_id(self):
        env,roots,_,_=make_policy(modifications=lambda b:b['keys'].append(dict(b['keys'][0])))
        self.bad(env,roots,'INVALID_SIGNER_ENTRY')

    def test_alias_public_key(self):
        def mod(b): b['keys'][1]['public_key_hex']=b['keys'][0]['public_key_hex']
        env,roots,_,_=make_policy(modifications=mod)
        self.bad(env,roots,'DUPLICATE_SIGNER_KEY_MATERIAL')

    def test_role_escalation_but_signed_by_root_disallowed(self):
        def mod(b):b['keys'][0]['role']='administrator'
        env,roots,_,_=make_policy(modifications=mod)
        self.bad(env,roots,'INVALID_SIGNER_ENTRY')

    def test_noncanonical_signed_policy(self):
        env,roots,root,_=make_policy()
        env.canonical_policy_json=b' '+env.canonical_policy_json
        env.ed25519_signature=root.sign(P8_DOMAIN+env.canonical_policy_json)
        self.bad(env,roots,'NONCANONICAL_POLICY')

    def test_grants_authority_denied(self):
        env,roots,_,_=make_policy()
        env.grants_authority=True
        self.bad(env,roots,'INVALID_P8_CONTRACT')

    def test_genesis_and_upgrade(self):
        env,roots,root,keys=make_policy()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'witness.sqlite'
            snap,result=advance_policy_highwater(env,roots,path)
            self.assertFalse(result.persistent_highwater_verified)
            host=HostHighwater(snap.generation,snap.policy_sha256)
            same,result=advance_policy_highwater(env,roots,path,host)
            self.assertTrue(result.persistent_highwater_verified)
            nxt,_,_,_=make_policy(prior=snap.policy_sha256,keys=keys,root=root,generation=2)
            latest,_=advance_policy_highwater(nxt,roots,path,host)
            self.assertEqual(latest.generation,2)
            with self.assertRaisesRegex(T4Rejected,'POLICY_ROLLBACK_OR_BROKEN_CHAIN'):
                advance_policy_highwater(env,roots,path)
            with self.assertRaisesRegex(T4Rejected,'HOST_WITNESS_DIVERGENCE'):
                advance_policy_highwater(nxt,roots,path,host)

    def test_equivocation_same_generation(self):
        env,roots,root,keys=make_policy()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'w.sqlite'
            advance_policy_highwater(env,roots,path)
            equiv,_,_,_=make_policy(keys=keys,root=root,modifications=lambda b:b['keys'][0].update(valid_until_ms=1790002000000))
            with self.assertRaisesRegex(T4Rejected,'POLICY_EQUIVOCATION'):
                advance_policy_highwater(equiv,roots,path)

    def test_non_genesis_new_database_fails(self):
        env,roots,_,_=make_policy(generation=2,prior='a'*64)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(T4Rejected,'POLICY_NON_GENESIS_UNANCHORED'):
                advance_policy_highwater(env,roots,Path(directory)/'w.sqlite')

    def test_tampered_host_database_detected(self):
        env,roots,_,_=make_policy()
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'w.sqlite'
            snap,_=advance_policy_highwater(env,roots,p)
            p.unlink()
            with self.assertRaisesRegex(T4Rejected,'HOST_WITNESS_DIVERGENCE'):
                advance_policy_highwater(env,roots,p,HostHighwater(1,snap.policy_sha256))

    def test_revoked_publisher_propagates_to_p5_p7(self):
        p7,_,keys=create()
        def mod(body):
            for e in body['keys']:
                if e['key_id']=='publisher':e['revoked']=True
        env,roots,_,_=make_policy(keys=keys,modifications=mod)
        from cognitum.spatial_functional_material_p5_p7 import evaluate_p7
        with self.assertRaisesRegex(T4Rejected,'REVOKED_SIGNER'):
            evaluate_p7(p7,policy_snapshot(env,roots).signers)


class P9TimeNotaryTests(unittest.TestCase):
    def bad(self,q,snap,code):
        with self.assertRaisesRegex(T4Rejected,code):evaluate_p9(q,snap)

    def test_valid_fixture_notary(self):
        q,snap,_=make_p9()
        out=evaluate_p9(q,snap)
        self.assertTrue(out.signed_notary_anchor_verified)
        self.assertFalse(out.externally_issued_timestamp_verified)
        self.assertFalse(out.independent_preregistration_verified)
        self.assertFalse(out.grants_authority)

    def test_notary_signature_corrupted(self):
        q,snap,_=make_p9()
        q.notary_statement.ed25519_signature=b'\x00'*64
        self.bad(q,snap,'INVALID_ED25519_SIGNATURE')

    def test_notary_over_wrong_p6_digest(self):
        q,snap,keys=make_p9()
        signed(q.notary_statement,keys['notary'],P9_DOMAIN,dict(
            schema_version=1,study_id=q.p7.p6.p5.p4.p3_audit.study_id,
            p6_sha256='f'*64,issued_at_ms=1790000000500,notary_sequence=1))
        self.bad(q,snap,'NOTARY_CONTEXT_MISMATCH')

    def test_notary_signed_backdated_not_a_proven_timestamp(self):
        q,snap,_=make_p9()
        out=evaluate_p9(q,snap)
        self.assertFalse(out.externally_issued_timestamp_verified)

    def test_notary_issued_after_observation(self):
        q,snap,keys=make_p9()
        data=json.loads(q.notary_statement.statement_json)
        data['issued_at_ms']=1790000001000
        signed(q.notary_statement,keys['notary'],P9_DOMAIN,data)
        self.bad(q,snap,'NOTARY_NOT_BEFORE_OBSERVATIONS')

    def test_notary_before_lock(self):
        q,snap,keys=make_p9()
        data=json.loads(q.notary_statement.statement_json)
        data['issued_at_ms']=1789999999500
        signed(q.notary_statement,keys['notary'],P9_DOMAIN,data)
        self.bad(q,snap,'NOTARY_NOT_BEFORE_OBSERVATIONS')

    def test_notary_revocation(self):
        q,snap,_=make_p9()
        from dataclasses import replace
        policy=dict(snap.signers)
        policy['notary']=replace(policy['notary'],revoked=True)
        snap=replace(snap,signers=policy)
        self.bad(q,snap,'REVOKED_SIGNER')

    def test_prior_p7_failure_still_fails(self):
        q,snap,_=make_p9()
        q.p7.reviewer_statements[0].ed25519_signature=b'\x00'*64
        self.bad(q,snap,'INVALID_ED25519_SIGNATURE')

    def test_notary_fails_cross_role(self):
        q,snap,_=make_p9()
        q.notary_statement.key_id='publisher'
        self.bad(q,snap,'SIGNER_NOT_TRUSTED_FOR_ROLE')

    def test_notary_authority_request_fails(self):
        q,snap,_=make_p9()
        q.grants_authority=True
        self.bad(q,snap,'INVALID_P9_CONTRACT')


class P10DatasetIntakeTests(unittest.TestCase):
    def bad(self,q,code,allowed=('synthetic_fixture',)):
        with self.assertRaisesRegex(T4Rejected,code):evaluate_p10(q,allowed)

    def test_structural_fixture(self):
        q,_=make_dataset()
        out=evaluate_p10(q,{'synthetic_fixture'})
        self.assertEqual((out.rows_validated,out.specimen_groups,out.calibrations_bound),(2,2,1))
        self.assertTrue(out.csv_digest_verified)
        self.assertFalse(out.licensed_real_world_data_verified)
        self.assertFalse(out.calibration_independently_verified)

    def test_csv_bitflip(self):
        q,_=make_dataset();q.raw_csv+=b' '
        self.bad(q,'DATASET_HASH_MISMATCH')

    def test_unapproved_license(self):
        q,_=make_dataset()
        self.bad(q,'LICENSE_NOT_APPROVED_BY_HOST',allowed={'actual_unrelated_license'})

    def test_corrupt_calibration(self):
        q,_=make_dataset();q.calibration_documents[0].content+=b'junk'
        self.bad(q,'CALIBRATION_CONTENT_HASH_MISMATCH')

    def test_holdout_group_leakage(self):
        q,m=make_dataset();q.raw_csv=q.raw_csv.replace(b's2,g2,holdout',b's2,g1,holdout')
        m['raw_csv_sha256']=sha(q.raw_csv);q.manifest_json=canonical(m)
        self.bad(q,'DATASET_PARTITION_LEAKAGE')

    def test_nan_rejected(self):
        q,m=make_dataset();q.raw_csv=q.raw_csv.replace(b'-0.25',b'NaN')
        m['raw_csv_sha256']=sha(q.raw_csv);q.manifest_json=canonical(m)
        self.bad(q,'INVALID_MEASUREMENT')

    def test_duplicate_specimen_rejected(self):
        q,m=make_dataset();q.raw_csv=q.raw_csv.replace(b's2,g2',b's1,g2')
        m['raw_csv_sha256']=sha(q.raw_csv);q.manifest_json=canonical(m)
        self.bad(q,'INVALID_SPECIMEN_ROW')

    def test_extra_csv_column(self):
        q,m=make_dataset();q.raw_csv=q.raw_csv.replace(b'1.5,cal1',b'1.5,cal1,extra')
        m['raw_csv_sha256']=sha(q.raw_csv);q.manifest_json=canonical(m)
        self.bad(q,'INVALID_CSV_ROW')

    def test_unknown_field_claiming_certification(self):
        q,m=make_dataset();m['safe_for_deployment']=True;q.manifest_json=canonical(m)
        self.bad(q,'UNEXPECTED_OR_MISSING_JSON_FIELD')

    def test_no_calibration_document(self):
        q,_=make_dataset();q.calibration_documents.clear()
        self.bad(q,'INVALID_DATASET_BOUNDS')

    def test_unauthorized_action(self):
        q,_=make_dataset();q.grants_authority=True
        self.bad(q,'INVALID_P10_CONTRACT')

    def test_wire_roundtrip(self):
        q,_=make_dataset()
        other=w.T4P10DatasetIntakeRequest.FromString(q.SerializeToString())
        self.assertEqual(evaluate_p10(q,{'synthetic_fixture'}),
                         evaluate_p10(other,{'synthetic_fixture'}))

if __name__=='__main__':unittest.main()

class P8DurableRevocationTests(unittest.TestCase):
    def test_revocation_tombstone_no_resurrection(self):
        env,roots,root,keys=make_policy()
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'w.sqlite'
            snap,_=advance_policy_highwater(env,roots,db)
            prior=snap.policy_sha256
            body=json.loads(env.canonical_policy_json)
            body['generation']=2;body['previous_sha256']=prior
            for e in body['keys']:
                if e['key_id']=='publisher':e['revoked']=True
            revoked=w.T4TrustPolicyEnvelope(schema_version=1,research_only=True,root_key_id='fixture_root')
            revoked.canonical_policy_json=canonical(body)
            revoked.ed25519_signature=root.sign(P8_DOMAIN+revoked.canonical_policy_json)
            two,_=advance_policy_highwater(revoked,roots,db)
            body['generation']=3;body['previous_sha256']=two.policy_sha256
            for e in body['keys']:
                if e['key_id']=='publisher':e['revoked']=False
            reinstated=w.T4TrustPolicyEnvelope(schema_version=1,research_only=True,root_key_id='fixture_root')
            reinstated.canonical_policy_json=canonical(body)
            reinstated.ed25519_signature=root.sign(P8_DOMAIN+reinstated.canonical_policy_json)
            with self.assertRaisesRegex(T4Rejected,'REVOCATION_UNDO_DENIED'):
                advance_policy_highwater(reinstated,roots,db)

    def test_revocation_tombstone_cannot_be_erased(self):
        env,roots,root,keys=make_policy()
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'w.sqlite'
            one,_=advance_policy_highwater(env,roots,db)
            body=json.loads(env.canonical_policy_json)
            body['generation']=2;body['previous_sha256']=one.policy_sha256
            body['keys']=[k for k in body['keys'] if k['key_id']!='publisher']
            next_env=w.T4TrustPolicyEnvelope(schema_version=1,research_only=True,root_key_id='fixture_root')
            next_env.canonical_policy_json=canonical(body)
            next_env.ed25519_signature=root.sign(P8_DOMAIN+next_env.canonical_policy_json)
            with self.assertRaisesRegex(T4Rejected,'SIGNER_TOMBSTONE_REMOVAL'):
                advance_policy_highwater(next_env,roots,db)
