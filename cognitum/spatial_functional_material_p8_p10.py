"""C15 T4 P8-P10: host-pinned signer policy, claimed notary time, staged CSV intake.

Caution: Ed25519 signature != external identity, notary's claimed time !=
independent TSA, SQLite highwater != protected hardware monotonic storage,
and licensed/structurally valid CSV != genuine physical measurement.
The host MUST supply root keys, current highwater, and allowed license IDs.
No network I/O, physical activity, or Lu changes. The optional SQLite witness
can be run only by a trusted host; the model must never write its database.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
import re
import sqlite3
from typing import Mapping, Collection

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cognitum.proto import spatial_functional_material_p8_p10_pb2 as wire
from cognitum.spatial_functional_material import T4Rejected, _ident, _no_unknown
from cognitum.spatial_functional_material_p4 import _parse, _strict_keys
from cognitum.spatial_functional_material_p5_p7 import (
    TrustedSigner, canonical, sha, strict_time, statement, ensure,
    base_contract, evaluate_p7, _lock,
)

P8_DOMAIN = b'C15-T4-P8-HOST-POLICY-V1\x00'
P9_DOMAIN = b'C15-T4-P9-NOTARY-V1\x00'
MAX_POLICY = 32768
MAX_ROWS = 160
MAX_CSV = 750000
MAX_MANIFEST = 16384
MAX_CALIBRATION = 65536
ROLES = frozenset({'publisher','plan_attestor','reviewer','time_notary'})
SHA256_HEX = re.compile(r'[0-9a-f]{64}\Z')


@dataclass(frozen=True)
class PolicySnapshot:
    policy_id: str
    generation: int
    policy_sha256: str
    previous_sha256: str
    signers: Mapping[str, TrustedSigner]
    root_key_id: str


@dataclass(frozen=True)
class HostHighwater:
    """Host-held *external* state; never derive this solely from a model request."""
    generation: int
    policy_sha256: str


def policy_snapshot(envelope: wire.T4TrustPolicyEnvelope,
                    pinned_roots: Mapping[str, bytes]) -> PolicySnapshot:
    base_contract(envelope, wire.T4TrustPolicyEnvelope, 'P8')
    ensure(_ident(envelope.root_key_id) and len(envelope.ed25519_signature)==64,
           'INVALID_POLICY_ENVELOPE')
    ensure(envelope.root_key_id in pinned_roots, 'UNPINNED_POLICY_ROOT')
    root=pinned_roots[envelope.root_key_id]
    ensure(type(root) is bytes and len(root)==32, 'INVALID_PINNED_ROOT')
    obj=_parse(envelope.canonical_policy_json, MAX_POLICY, 'INVALID_POLICY_JSON')
    _strict_keys(obj, {'schema_version','policy_id','generation','previous_sha256','keys'})
    ensure(canonical(obj)==envelope.canonical_policy_json,'NONCANONICAL_POLICY')
    try:
        Ed25519PublicKey.from_public_bytes(root).verify(envelope.ed25519_signature,
                                                P8_DOMAIN+envelope.canonical_policy_json)
    except (InvalidSignature, ValueError) as exc:
        raise T4Rejected('INVALID_ROOT_SIGNATURE') from exc
    ensure(type(obj['schema_version']) is int and obj['schema_version']==1 and
           type(obj['policy_id']) is str and _ident(obj['policy_id']) and
           type(obj['generation']) is int and 1<=obj['generation']<=2**63-1 and
           type(obj['previous_sha256']) is str and
           SHA256_HEX.fullmatch(obj['previous_sha256']) is not None and
           type(obj['keys']) is list and 1<=len(obj['keys'])<=64,
           'INVALID_POLICY_CONTENT')
    if obj['generation']==1:
        ensure(obj['previous_sha256']=='0'*64, 'INVALID_GENESIS_LINK')
    signers={}
    materials={root}
    for entry in obj['keys']:
        ensure(type(entry) is dict, 'INVALID_SIGNER_ENTRY')
        _strict_keys(entry, {'key_id','role','public_key_hex','valid_from_ms','valid_until_ms','revoked'})
        key_id=entry['key_id']
        ensure(type(key_id) is str and _ident(key_id) and key_id not in signers and
               key_id != envelope.root_key_id and type(entry['role']) is str and
               entry['role'] in ROLES and type(entry['revoked']) is bool and
               type(entry['public_key_hex']) is str and
               re.fullmatch('[0-9a-f]{64}',entry['public_key_hex']) is not None,
               'INVALID_SIGNER_ENTRY')
        material=bytes.fromhex(entry['public_key_hex'])
        ensure(material not in materials, 'DUPLICATE_SIGNER_KEY_MATERIAL')
        materials.add(material)
        start=strict_time(entry['valid_from_ms'])
        end=strict_time(entry['valid_until_ms'])
        ensure(start<end,'INVALID_SIGNER_WINDOW')
        signers[key_id]=TrustedSigner(entry['role'],material,start,end,entry['revoked'])
    return PolicySnapshot(obj['policy_id'],obj['generation'],sha(envelope.canonical_policy_json),
                          obj['previous_sha256'],signers,envelope.root_key_id)


def advance_policy_highwater(envelope: wire.T4TrustPolicyEnvelope,
                             pinned_roots: Mapping[str,bytes],
                             sqlite_db: str|Path,
                             host_minimum: HostHighwater|None=None):
    """Trusted-host-only BEGIN IMMEDIATE SQLite monotonic journal.

    Host must authenticate the DB path and supply a separately protected
    previous highwater to defend against rollback of the *whole* SQLite DB.
    A fresh database cannot prove that previous states never existed.
    """
    snap=policy_snapshot(envelope,pinned_roots)
    if host_minimum is not None:
        ensure(isinstance(host_minimum,HostHighwater) and
               type(host_minimum.generation) is int and host_minimum.generation>=1 and
               type(host_minimum.policy_sha256) is str and
               SHA256_HEX.fullmatch(host_minimum.policy_sha256) is not None,
               'INVALID_HOST_CHECKPOINT')
    p=Path(sqlite_db)
    ensure(p.parent.is_dir(), 'HOST_WITNESS_PARENT_MISSING')
    with sqlite3.connect(str(p),timeout=5,isolation_level=None) as db:
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('CREATE TABLE IF NOT EXISTS policy_highwater ('
                       'policy_id TEXT PRIMARY KEY, generation INTEGER NOT NULL, '
                       'digest TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS policy_signers ('
                       'policy_id TEXT NOT NULL, key_id TEXT NOT NULL, '
                       'role TEXT NOT NULL, material BLOB NOT NULL, revoked INTEGER NOT NULL, '
                       'PRIMARY KEY(policy_id,key_id))')
            prior=db.execute('SELECT generation,digest FROM policy_highwater WHERE policy_id=?',
                             (snap.policy_id,)).fetchone()
            prior_signers={row[0]:row[1:] for row in db.execute(
                'SELECT key_id,role,material,revoked FROM policy_signers WHERE policy_id=?',
                (snap.policy_id,)).fetchall()}
            if host_minimum is not None:
                ensure(prior is not None and prior==(host_minimum.generation,
                       host_minimum.policy_sha256), 'HOST_WITNESS_DIVERGENCE')
            if prior is None:
                ensure(snap.generation==1 and snap.previous_sha256=='0'*64,
                       'POLICY_NON_GENESIS_UNANCHORED')
            elif snap.generation==prior[0]:
                ensure(snap.policy_sha256==prior[1], 'POLICY_EQUIVOCATION')
            else:
                ensure(snap.generation==prior[0]+1 and snap.previous_sha256==prior[1],
                       'POLICY_ROLLBACK_OR_BROKEN_CHAIN')
            if prior is not None:
                # Revocation is irreversible within a policy. Revoked key IDs
                # remain signed tombstones; changing an ID's key/role is
                # forbidden, including during later signed generations.
                for key_id,(role,material,revoked) in prior_signers.items():
                    ensure(key_id in snap.signers,'SIGNER_TOMBSTONE_REMOVAL')
                    current=snap.signers[key_id]
                    ensure(current.role==role and current.public_key==material,
                           'SIGNER_IDENTITY_MUTATION')
                    ensure(not revoked or current.revoked,'REVOCATION_UNDO_DENIED')
                ensure(set(prior_signers)==set(snap.signers) if
                       snap.generation==prior[0] else True,
                       'POLICY_SIGNER_STORE_DIVERGENCE')
            if prior is None or snap.generation>prior[0]:
                for key_id,signer in snap.signers.items():
                    db.execute('INSERT INTO policy_signers('
                               'policy_id,key_id,role,material,revoked) VALUES (?,?,?,?,?) '
                               'ON CONFLICT(policy_id,key_id) DO UPDATE SET '
                               'role=excluded.role,material=excluded.material,'
                               'revoked=excluded.revoked',
                               (snap.policy_id,key_id,signer.role,signer.public_key,
                                int(signer.revoked)))
                db.execute('INSERT INTO policy_highwater(policy_id,generation,digest) VALUES (?,?,?) '
                           'ON CONFLICT(policy_id) DO UPDATE SET generation=excluded.generation, '
                           'digest=excluded.digest',
                           (snap.policy_id,snap.generation,snap.policy_sha256))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
    return snap,wire.T4TrustPolicyResult(
        generation=snap.generation,policy_sha256=snap.policy_sha256,
        active_signers=sum(not k.revoked for k in snap.signers.values()),
        revoked_signers=sum(k.revoked for k in snap.signers.values()),
        host_root_signature_verified=True,
        persistent_highwater_verified=host_minimum is not None,
        independent_identity_verified=False,research_only=True,grants_authority=False,
        warnings=[
            'SQLITE_ALONE_IS_NOT_PROTECTED_FROM_HOST_STORAGE_ROLLBACK',
            'EXTERNAL_SIGNER_IDENTITY_AND_KEY_ENROLLMENT_NOT_VERIFIED',
            'HOST_HIGHWATER_IS_NOT_HARDWARE_MONOTONIC_COUNTER',
            'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])


def evaluate_p9(req: wire.T4P9TimeAnchorRequest,
                snapshot: PolicySnapshot) -> wire.T4P9TimeAnchorResult:
    base_contract(req,wire.T4P9TimeAnchorRequest,'P9')
    ensure(isinstance(snapshot,PolicySnapshot) and req.HasField('p7') and
           req.HasField('notary_statement'),'MISSING_P9_CONTEXT')
    # Validate all P4-P7 gates under the *same* host verified policy generation.
    prior=evaluate_p7(req.p7,snapshot.signers)
    _, sources, lock_time=_lock(req.p7.p6,snapshot.signers)
    obj=statement(req.notary_statement,P9_DOMAIN,'time_notary',
                  {'schema_version','study_id','p6_sha256','issued_at_ms','notary_sequence'},
                  snapshot.signers,'issued_at_ms')
    ensure(type(obj['study_id']) is str and
           obj['study_id']==req.p7.p6.p5.p4.p3_audit.study_id and
           type(obj['p6_sha256']) is str and
           obj['p6_sha256']==sha(req.p7.p6.SerializeToString(deterministic=True)),
           'NOTARY_CONTEXT_MISMATCH')
    ensure(type(obj['notary_sequence']) is int and 1<=obj['notary_sequence']<=2**63-1,
           'INVALID_NOTARY_SEQUENCE')
    ensure(lock_time<=obj['issued_at_ms'] and
           all(obj['issued_at_ms']<timestamp for _,timestamp in sources.values()),
           'NOTARY_NOT_BEFORE_OBSERVATIONS')
    notary_material=snapshot.signers[req.notary_statement.key_id].public_key
    all_other_keys={s.key_id for s in req.p7.p6.p5.source_statements}
    all_other_keys.add(req.p7.p6.plan_lock.key_id)
    all_other_keys.update(s.key_id for s in req.p7.reviewer_statements)
    ensure(req.notary_statement.key_id not in all_other_keys and
           all(snapshot.signers[k].public_key!=notary_material for k in all_other_keys),
           'NOTARY_KEY_NOT_SEPARATE')
    result=wire.T4P9TimeAnchorResult(
        signed_notary_anchor_verified=True,
        externally_issued_timestamp_verified=False,
        independent_preregistration_verified=False,
        research_only=True,grants_authority=False,
        warnings=['NOTARY_CLAIMED_TIME_NOT_INDEPENDENT_RFC3161_OR_TRANSPARENCY_PROOF',
                  'NOTARY_SEQUENCE_NOT_AN_EXTERNALLY_MONOTONIC_WITNESS',
                  'EXTERNAL_KEY_IDENTITY_AND_REAL_EXPERT_REVIEW_NOT_ESTABLISHED',
                  'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
    result.p7_result.CopyFrom(prior)
    return result


CSV_FIELDS=('specimen_id','group_id','partition','observed_class',
            'measured_clearance_m','calibration_id')


def evaluate_p10(req: wire.T4P10DatasetIntakeRequest,
                 host_allowed_license_ids: Collection[str]) -> wire.T4P10DatasetIntakeResult:
    base_contract(req,wire.T4P10DatasetIntakeRequest,'P10')
    ensure(len(req.raw_csv)<=MAX_CSV and 1<=len(req.calibration_documents)<=32 and
           len(req.SerializeToString())<=1_500_000,'INVALID_DATASET_BOUNDS')
    manifest=_parse(req.manifest_json,MAX_MANIFEST,'INVALID_DATASET_MANIFEST')
    _strict_keys(manifest, {'schema_version','dataset_id','study_id','raw_csv_sha256',
                            'declared_source_uri','declared_license_id','units',
                            'partition_policy','calibration_sha256_by_id','intended_use'})
    ensure(canonical(manifest)==req.manifest_json and
           type(manifest['schema_version']) is int and manifest['schema_version']==1 and
           all(type(manifest[k]) is str and _ident(manifest[k]) for k in
               ('dataset_id','study_id','declared_license_id')) and
           type(manifest['declared_source_uri']) is str and
           1<=len(manifest['declared_source_uri'])<=512 and
           manifest['units']=='m' and manifest['partition_policy']=='group_isolated' and
           manifest['intended_use']=='research_only', 'INVALID_DATASET_MANIFEST')
    ensure(type(manifest['raw_csv_sha256']) is str and
           manifest['raw_csv_sha256']==sha(req.raw_csv), 'DATASET_HASH_MISMATCH')
    ensure(type(host_allowed_license_ids) in (set,frozenset,tuple,list) and
           manifest['declared_license_id'] in host_allowed_license_ids,
           'LICENSE_NOT_APPROVED_BY_HOST')
    digests=manifest['calibration_sha256_by_id']
    ensure(type(digests) is dict and 1<=len(digests)<=32,
           'INVALID_CALIBRATION_MANIFEST')
    calibrations={}
    for blob in req.calibration_documents:
        ensure(_no_unknown(blob) and _ident(blob.ref_id) and
               blob.ref_id not in calibrations and 0<len(blob.content)<=MAX_CALIBRATION,
               'INVALID_CALIBRATION_BLOB')
        calibrations[blob.ref_id]=sha(blob.content)
    ensure(set(calibrations)==set(digests) and
           all(type(value) is str and SHA256_HEX.fullmatch(value) and
               calibrations[key]==value for key,value in digests.items()),
           'CALIBRATION_CONTENT_HASH_MISMATCH')
    try:
        raw=req.raw_csv.decode('utf-8',errors='strict')
        ensure('\x00' not in raw and '\r' not in raw and not raw.startswith('\ufeff'),
               'INVALID_CSV_BYTES')
        reader=csv.reader(io.StringIO(raw,newline=''),strict=True)
        header=next(reader)
        ensure(tuple(header)==CSV_FIELDS,'INVALID_CSV_HEADER')
        seen=set();groups={};used=set();count=0
        for row in reader:
            count+=1
            ensure(count<=MAX_ROWS and len(row)==len(CSV_FIELDS), 'INVALID_CSV_ROW')
            specimen,group,partition,label,num,cal=row
            ensure(all(_ident(x) for x in (specimen,group,cal)) and
                   specimen not in seen and cal in calibrations and
                   partition in ('calibration','holdout') and
                   label in ('satisfies','violates','undetermined'),
                   'INVALID_SPECIMEN_ROW')
            seen.add(specimen);used.add(cal)
            ensure(group not in groups or groups[group]==partition,
                   'DATASET_PARTITION_LEAKAGE')
            groups[group]=partition
            try: value=float(num)
            except ValueError as exc: raise T4Rejected('INVALID_MEASUREMENT') from exc
            ensure(num.strip()==num and num and math.isfinite(value) and
                   abs(value)<=1_000_000,'INVALID_MEASUREMENT')
        ensure(1<=count<=MAX_ROWS and used==set(calibrations),
               'INCOMPLETE_CALIBRATION_BINDINGS')
    except T4Rejected:
        raise
    except (ValueError,csv.Error,UnicodeError,StopIteration) as exc:
        raise T4Rejected('INVALID_CSV_FORMAT') from exc
    return wire.T4P10DatasetIntakeResult(
        rows_validated=count,specimen_groups=len(groups),calibrations_bound=len(calibrations),
        csv_digest_verified=True,licensed_real_world_data_verified=False,
        calibration_independently_verified=False,physical_safety_verified=False,
        research_only=True,grants_authority=False,
        warnings=['ALLOWLISTED_LICENSE_ID_DOES_NOT_PROVE_LEGAL_REUSE_RIGHTS',
                  'CALIBRATION_HASH_DOES_NOT_CERTIFY_INSTRUMENT',
                  'CSV_NUMBERS_HAVE_NOT_BEEN_VALIDATED_AGAINST_REAL_MEASUREMENTS',
                  'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
