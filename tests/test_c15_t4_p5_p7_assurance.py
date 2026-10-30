"""P5/P6/P7 cryptographic assurance under SYNTHETIC host-supplied trust fixtures."""
from __future__ import annotations
import copy
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from cognitum.proto import spatial_functional_material_p5_p7_pb2 as w
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p5_p7 import (
    TrustedSigner, P5_DOMAIN, P6_DOMAIN, P7_DOMAIN, canonical, sha,
    evaluate_p5, evaluate_p6, evaluate_p7)
from tests.test_c15_t4_p4_evidence_gate import build

LOCK=1790000000000
OBS=1790000001000
REVIEW=1790000002000


def signed(rec, private, domain, payload):
    rec.statement_json=canonical(payload)
    rec.ed25519_signature=private.sign(domain+rec.statement_json)


def create(n=2,p4_request=None):
    priv={s:Ed25519PrivateKey.generate() for s in ('publisher','lock','review_a','review_b')}
    role={'publisher':'publisher', 'lock':'plan_attestor',
          'review_a':'reviewer','review_b':'reviewer'}
    policy={name:TrustedSigner(role[name],key.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw),
        1789999999000,1790001000000) for name,key in priv.items()}
    q=w.T4P7AdjudicationRequest(schema_version=1,research_only=True)
    q.p6.schema_version=1; q.p6.research_only=True
    q.p6.p5.schema_version=1; q.p6.p5.research_only=True
    q.p6.p5.p4.CopyFrom(p4_request if p4_request is not None else build(n))
    p4=q.p6.p5.p4
    study=p4.p3_audit.study_id
    for ref in p4.references:
        record=q.p6.p5.source_statements.add(key_id='publisher')
        signed(record,priv['publisher'],P5_DOMAIN,dict(
            schema_version=1,case_id=ref.case_id,study_id=study,
            plan_sha256=sha(p4.frozen_plan_json),payload_sha256=sha(ref.reference_payload),
            source_uri=ref.source_uri,license_id=ref.license_id,
            calibration_record_ref=ref.calibration_record_ref,observed_at_ms=OBS))
    q.p6.plan_lock.key_id='lock'
    signed(q.p6.plan_lock,priv['lock'],P6_DOMAIN,dict(
        schema_version=1,study_id=study,
        plan_sha256=sha(p4.frozen_plan_json),locked_at_ms=LOCK))
    for ref in p4.references:
        for reviewer in ('review_a','review_b'):
            rec=q.reviewer_statements.add(key_id=reviewer)
            signed(rec,priv[reviewer],P7_DOMAIN,dict(
                schema_version=1,case_id=ref.case_id,study_id=study,
                payload_sha256=sha(ref.reference_payload),
                observed_class=json.loads(ref.reference_payload)['observed_class'],reviewed_at_ms=REVIEW,
                review_protocol_id='synthetic_blind_protocol',
                blind_to_model_prediction=True))
    return q,policy,priv


def rewrite(rec, priv, domain, **changes):
    obj=json.loads(rec.statement_json)
    obj.update(changes)
    signed(rec,priv[rec.key_id],domain,obj)


class P5SignatureGateTests(unittest.TestCase):
    def rejected(self,req,policy,code):
        with self.assertRaisesRegex(T4Rejected,code): evaluate_p5(req,policy)

    def test_valid_signatures_under_synthetic_policy(self):
        q,policy,_=create()
        out=evaluate_p5(q.p6.p5,policy)
        self.assertEqual(out.source_signatures_verified,2)
        self.assertTrue(out.trusted_policy_signatures_verified)
        self.assertTrue(out.p4_result.payload_integrity_verified)
        self.assertFalse(out.external_publisher_identity_verified)
        self.assertFalse(out.physical_measurements_verified)
        self.assertFalse(out.grants_authority)

    def test_wire_roundtrip(self):
        q,policy,_=create()
        req=w.T4P5ProvenanceRequest.FromString(q.p6.p5.SerializeToString())
        self.assertEqual(evaluate_p5(q.p6.p5,policy),evaluate_p5(req,policy))

    def test_payload_tampering_denied_by_p4(self):
        q,policy,_=create()
        q.p6.p5.p4.references[0].reference_payload+=b' '
        self.rejected(q.p6.p5,policy,'REFERENCE_CONTENT_HASH_MISMATCH')

    def test_signed_receipt_tampering_invalid_signature(self):
        q,policy,_=create()
        q.p6.p5.source_statements[0].ed25519_signature=b'\x00'*64
        self.rejected(q.p6.p5,policy,'INVALID_ED25519_SIGNATURE')

    def test_signed_source_hash_wrong_with_valid_signature(self):
        q,policy,keys=create()
        rewrite(q.p6.p5.source_statements[0],keys,P5_DOMAIN,payload_sha256='ab'*32)
        self.rejected(q.p6.p5,policy,'SOURCE_SIGNATURE_BINDING_MISMATCH')

    def test_plan_digest_wrong_signed(self):
        q,policy,keys=create()
        rewrite(q.p6.p5.source_statements[0],keys,P5_DOMAIN,plan_sha256='ff'*32)
        self.rejected(q.p6.p5,policy,'SOURCE_SIGNATURE_BINDING_MISMATCH')

    def test_revoked_signer(self):
        q,policy,_=create()
        pub=policy['publisher']
        policy['publisher']=TrustedSigner(pub.role,pub.public_key,pub.valid_from_ms,pub.valid_until_ms,True)
        self.rejected(q.p6.p5,policy,'REVOKED_SIGNER')

    def test_unknown_signer(self):
        q,policy,_=create()
        del policy['publisher']
        self.rejected(q.p6.p5,policy,'SIGNER_NOT_TRUSTED_FOR_ROLE')

    def test_wrong_role_in_policy(self):
        q,policy,_=create()
        pub=policy['publisher']
        policy['publisher']=TrustedSigner('reviewer',pub.public_key,pub.valid_from_ms,pub.valid_until_ms)
        self.rejected(q.p6.p5,policy,'SIGNER_NOT_TRUSTED_FOR_ROLE')

    def test_signer_validity_window(self):
        q,policy,_=create()
        pub=policy['publisher']
        policy['publisher']=TrustedSigner(pub.role,pub.public_key,OBS+1,OBS+1000)
        self.rejected(q.p6.p5,policy,'SIGNER_OUTSIDE_VALIDITY')

    def test_missing_receipt(self):
        q,policy,_=create()
        del q.p6.p5.source_statements[-1]
        self.rejected(q.p6.p5,policy,'MISSING_SOURCE_SIGNATURE')

    def test_duplicate_signed_receipt(self):
        q,policy,_=create()
        q.p6.p5.source_statements[1].CopyFrom(q.p6.p5.source_statements[0])
        self.rejected(q.p6.p5,policy,'DUPLICATE_SOURCE_SIGNATURE')

    def test_noncanonical_json_even_when_validly_signed(self):
        q,policy,keys=create()
        rec=q.p6.p5.source_statements[0]
        rec.statement_json=b'{  '+rec.statement_json[1:]
        rec.ed25519_signature=keys[rec.key_id].sign(P5_DOMAIN+rec.statement_json)
        self.rejected(q.p6.p5,policy,'NONCANONICAL_SIGNED_STATEMENT')

    def test_invalid_timestamp_type_even_when_validly_signed(self):
        q,policy,keys=create()
        rewrite(q.p6.p5.source_statements[0],keys,P5_DOMAIN,observed_at_ms=True)
        self.rejected(q.p6.p5,policy,'INVALID_SIGNED_TIME')

    def test_unknown_field(self):
        q,policy,keys=create()
        rewrite(q.p6.p5.source_statements[0],keys,P5_DOMAIN,physical_safety_certified=True)
        self.rejected(q.p6.p5,policy,'UNEXPECTED_OR_MISSING_JSON_FIELD')

    def test_request_authority_denied(self):
        q,policy,_=create();q.p6.p5.grants_authority=True
        self.rejected(q.p6.p5,policy,'INVALID_P5_CONTRACT')

    def test_signature_cannot_be_reused_in_other_domain(self):
        q,policy,keys=create()
        rec=q.p6.p5.source_statements[0]
        rec.ed25519_signature=keys[rec.key_id].sign(P7_DOMAIN+rec.statement_json)
        self.rejected(q.p6.p5,policy,'INVALID_ED25519_SIGNATURE')

class P6PlanLockGateTests(unittest.TestCase):
    def rejected(self,req,policy,code):
        with self.assertRaisesRegex(T4Rejected,code): evaluate_p6(req,policy)

    def test_signed_order_pass_without_independent_registration(self):
        q,policy,_=create()
        out=evaluate_p6(q.p6,policy)
        self.assertTrue(out.signed_timeline_consistent)
        self.assertFalse(out.independent_preregistration_verified)
        self.assertFalse(out.p5_result.external_publisher_identity_verified)
        self.assertFalse(out.grants_authority)

    def test_post_observation_plan_lock_denied(self):
        q,policy,keys=create()
        rewrite(q.p6.plan_lock,keys,P6_DOMAIN,locked_at_ms=OBS+1)
        self.rejected(q.p6,policy,'PLAN_NOT_LOCKED_BEFORE_OBSERVATION')

    def test_equal_time_denied(self):
        q,policy,keys=create()
        rewrite(q.p6.plan_lock,keys,P6_DOMAIN,locked_at_ms=OBS)
        self.rejected(q.p6,policy,'PLAN_NOT_LOCKED_BEFORE_OBSERVATION')

    def test_lock_wrong_plan_hash(self):
        q,policy,keys=create()
        rewrite(q.p6.plan_lock,keys,P6_DOMAIN,plan_sha256='de'*32)
        self.rejected(q.p6,policy,'PLAN_LOCK_BINDING_MISMATCH')

    def test_lock_wrong_study(self):
        q,policy,keys=create()
        rewrite(q.p6.plan_lock,keys,P6_DOMAIN,study_id='other')
        self.rejected(q.p6,policy,'PLAN_LOCK_BINDING_MISMATCH')

    def test_revoked_attestor(self):
        q,policy,_=create()
        v=policy['lock'];policy['lock']=TrustedSigner(v.role,v.public_key,v.valid_from_ms,v.valid_until_ms,True)
        self.rejected(q.p6,policy,'REVOKED_SIGNER')

    def test_same_identity_source_and_plan_denied(self):
        q,policy,keys=create()
        q.p6.plan_lock.key_id='publisher'
        rewrite(q.p6.plan_lock,keys,P6_DOMAIN)
        pub=policy['publisher'];policy['publisher']=TrustedSigner('plan_attestor',pub.public_key,pub.valid_from_ms,pub.valid_until_ms)
        # Changing role invalidates publisher attestations before role-separation check.
        self.rejected(q.p6,policy,'SIGNER_NOT_TRUSTED_FOR_ROLE')

    def test_wrong_lock_signature(self):
        q,policy,_=create()
        q.p6.plan_lock.ed25519_signature=b'\x42'*64
        self.rejected(q.p6,policy,'INVALID_ED25519_SIGNATURE')

    def test_plan_lock_missing(self):
        q,policy,_=create()
        q.p6.ClearField('plan_lock')
        self.rejected(q.p6,policy,'MISSING_PLAN_LOCK')

    def test_authority_denied(self):
        q,policy,_=create();q.p6.grants_authority=True
        self.rejected(q.p6,policy,'INVALID_P6_CONTRACT')

class P7ReviewGateTests(unittest.TestCase):
    def rejected(self,req,policy,code):
        with self.assertRaisesRegex(T4Rejected,code): evaluate_p7(req,policy)

    def test_two_reviewer_signed_consensus(self):
        q,policy,_=create()
        out=evaluate_p7(q,policy)
        self.assertEqual(out.reviewed_cases,2)
        self.assertEqual(out.verified_signatures,4)
        self.assertTrue(out.two_reviewer_consensus)
        self.assertFalse(out.actual_blinding_verified)
        self.assertFalse(out.qualified_expert_status_verified)
        self.assertFalse(out.licensed_real_world_data_verified)
        self.assertFalse(out.physical_safety_verified)
        self.assertFalse(out.grants_authority)

    def test_review_disagreement_denied(self):
        q,policy,keys=create()
        rewrite(q.reviewer_statements[0],keys,P7_DOMAIN,observed_class='violates')
        self.rejected(q,policy,'REVIEWER_DISAGREEMENT_REQUIRES_ADJUDICATION')

    def test_two_agree_but_mismatch_reference(self):
        q,policy,keys=create()
        for rec in q.reviewer_statements[:2]:
            rewrite(rec,keys,P7_DOMAIN,observed_class='violates')
        self.rejected(q,policy,'REVIEW_LABEL_CONTRADICTS_OBSERVATION')

    def test_duplicate_reviewer(self):
        q,policy,_=create()
        q.reviewer_statements[1].CopyFrom(q.reviewer_statements[0])
        self.rejected(q,policy,'DUPLICATE_REVIEWER_FOR_CASE')

    def test_missing_reviewer(self):
        q,policy,_=create()
        del q.reviewer_statements[-1]
        self.rejected(q,policy,'MISSING_DUAL_REVIEW')

    def test_premature_review(self):
        q,policy,keys=create()
        rewrite(q.reviewer_statements[0],keys,P7_DOMAIN,reviewed_at_ms=OBS-1)
        self.rejected(q,policy,'REVIEW_PRECEDES_REFERENCE_OR_LOCK')

    def test_unsigned_blinding_claim_denied(self):
        q,policy,keys=create()
        rewrite(q.reviewer_statements[0],keys,P7_DOMAIN,blind_to_model_prediction=False)
        self.rejected(q,policy,'REVIEW_PROTOCOL_NOT_DECLARED')

    def test_wrong_review_hash(self):
        q,policy,keys=create()
        rewrite(q.reviewer_statements[0],keys,P7_DOMAIN,payload_sha256='ab'*32)
        self.rejected(q,policy,'REVIEW_BINDING_MISMATCH')

    def test_revoked_reviewer(self):
        q,policy,_=create()
        v=policy['review_a'];policy['review_a']=TrustedSigner(v.role,v.public_key,v.valid_from_ms,v.valid_until_ms,True)
        self.rejected(q,policy,'REVOKED_SIGNER')

    def test_role_separation(self):
        q,policy,_=create()
        p=policy['review_a'];policy['review_a']=TrustedSigner('publisher',p.public_key,p.valid_from_ms,p.valid_until_ms)
        self.rejected(q,policy,'SIGNER_NOT_TRUSTED_FOR_ROLE')

    def test_review_case_identity_mismatch(self):
        q,policy,keys=create()
        rewrite(q.reviewer_statements[0],keys,P7_DOMAIN,case_id='unknown')
        self.rejected(q,policy,'UNKNOWN_REVIEW_CASE')

    def test_authority_denied(self):
        q,policy,_=create();q.grants_authority=True
        self.rejected(q,policy,'INVALID_P7_CONTRACT')

    def test_wire_roundtrip(self):
        q,policy,_=create()
        res=w.T4P7AdjudicationRequest.FromString(q.SerializeToString())
        self.assertEqual(evaluate_p7(res,policy),evaluate_p7(q,policy))

if __name__=='__main__': unittest.main()

class KeyAliasAttackTests(unittest.TestCase):
    def test_attestor_alias_same_key_bytes_different_key_id(self):
        q,policy,priv=create()
        # Host erroneously registers publisher material as an attestation key.
        pub=policy['publisher']
        policy['lock']=TrustedSigner('plan_attestor',pub.public_key,pub.valid_from_ms,pub.valid_until_ms)
        q.p6.plan_lock.ed25519_signature=priv['publisher'].sign(P6_DOMAIN+q.p6.plan_lock.statement_json)
        with self.assertRaisesRegex(T4Rejected,'PLAN_ATTESTOR_NOT_SEPARATE_FROM_SOURCE'):
            evaluate_p6(q.p6,policy)

    def test_reviewer_alias_same_key_bytes_different_key_id(self):
        q,policy,priv=create()
        a=policy['review_a']
        policy['review_b']=TrustedSigner('reviewer',a.public_key,a.valid_from_ms,a.valid_until_ms)
        for r in q.reviewer_statements:
            if r.key_id=='review_b':
                r.ed25519_signature=priv['review_a'].sign(P7_DOMAIN+r.statement_json)
        with self.assertRaisesRegex(T4Rejected,'DUPLICATE_REVIEWER_FOR_CASE'):
            evaluate_p7(q,policy)
