"""C15 T4 P5-P7: offline signed provenance, prereg order, and dual-review gates.

These verify *cryptographic statements* under a separate, host-supplied trust
policy, not identities, laboratory instruments, actual blinding, licenses,
timestamp authority, professional qualifications, or physical safety.
No file/network IO; no keys or permission records are created; no Lu mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cognitum.proto import spatial_functional_material_p5_p7_pb2 as wire
from cognitum.spatial_functional_material import T4Rejected, _ident, _no_unknown
from cognitum.spatial_functional_material_p4 import evaluate as p4_evaluate, _parse, _strict_keys

P5_DOMAIN = b'C15-T4-P5-SOURCE-V1\x00'
P6_DOMAIN = b'C15-T4-P6-LOCK-V1\x00'
P7_DOMAIN = b'C15-T4-P7-REVIEW-V1\x00'
MAX_STATEMENT = 8192
MAX_CASES = 160
MAX_REQUEST_SIZE = 5_000_000
MIN_EPOCH_MS = 946684800000  # 2000-01-01
MAX_EPOCH_MS = 4102444800000  # 2100-01-01

@dataclass(frozen=True)
class TrustedSigner:
    role: str  # publisher / plan_attestor / reviewer, controlled by external host
    public_key: bytes
    valid_from_ms: int
    valid_until_ms: int
    revoked: bool = False


def fail(code: str) -> None:
    raise T4Rejected(code)


def ensure(test: bool, code: str) -> None:
    if not test:
        fail(code)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def strict_time(value: Any) -> int:
    ensure(type(value) is int and MIN_EPOCH_MS <= value < MAX_EPOCH_MS,
           'INVALID_SIGNED_TIME')
    return value


def statement(rec: wire.T4SignedRecord, domain: bytes, role: str,
              required: set[str], trust: Mapping[str, TrustedSigner],
              time_field: str) -> dict[str, Any]:
    ensure(_no_unknown(rec) and _ident(rec.key_id) and len(rec.ed25519_signature) == 64,
           'INVALID_SIGNATURE_ENVELOPE')
    obj = _parse(rec.statement_json, MAX_STATEMENT, 'INVALID_SIGNED_STATEMENT')
    _strict_keys(obj, required)
    ensure(canonical(obj) == rec.statement_json, 'NONCANONICAL_SIGNED_STATEMENT')
    ensure(type(obj.get('schema_version')) is int and obj['schema_version'] == 1,
           'INVALID_SIGNED_SCHEMA')
    issued = strict_time(obj[time_field])
    key = trust.get(rec.key_id)
    ensure(key is not None and isinstance(key, TrustedSigner) and key.role == role,
           'SIGNER_NOT_TRUSTED_FOR_ROLE')
    ensure(not key.revoked, 'REVOKED_SIGNER')
    ensure(type(key.valid_from_ms) is int and type(key.valid_until_ms) is int and
           key.valid_from_ms <= issued <= key.valid_until_ms,
           'SIGNER_OUTSIDE_VALIDITY')
    ensure(type(key.public_key) is bytes and len(key.public_key) == 32,
           'INVALID_TRUST_POLICY_KEY')
    try:
        Ed25519PublicKey.from_public_bytes(key.public_key).verify(
            rec.ed25519_signature, domain + rec.statement_json)
    except (InvalidSignature, ValueError) as exc:
        raise T4Rejected('INVALID_ED25519_SIGNATURE') from exc
    return obj


def base_contract(req: Any, cls: type, name: str) -> None:
    ensure(isinstance(req, cls) and req.schema_version == 1 and
           req.research_only and not req.grants_authority and _no_unknown(req) and
           len(req.SerializeToString()) <= MAX_REQUEST_SIZE,
           'INVALID_' + name + '_CONTRACT')


def _sources(req: wire.T4P5ProvenanceRequest,
             policy: Mapping[str, TrustedSigner]):
    base_contract(req, wire.T4P5ProvenanceRequest, 'P5')
    ensure(req.HasField('p4') and 1 <= len(req.source_statements) <= MAX_CASES,
           'MISSING_P5_EVIDENCE')
    p4_result = p4_evaluate(req.p4)
    expected = {ref.case_id: ref for ref in req.p4.references}
    ensure(len(req.source_statements) == len(expected), 'MISSING_SOURCE_SIGNATURE')
    seen: set[str] = set()
    records: dict[str, tuple[str, int]] = {}
    study = req.p4.p3_audit.study_id
    plan_digest = sha(req.p4.frozen_plan_json)
    for rec in req.source_statements:
        obj = statement(rec, P5_DOMAIN, 'publisher',
                        {'schema_version','case_id','study_id','plan_sha256',
                         'payload_sha256','source_uri','license_id',
                         'calibration_record_ref','observed_at_ms'},
                        policy, 'observed_at_ms')
        case_id = obj['case_id']
        ensure(type(case_id) is str and _ident(case_id) and
               case_id in expected, 'UNKNOWN_SIGNED_CASE')
        ensure(case_id not in seen, 'DUPLICATE_SOURCE_SIGNATURE')
        seen.add(case_id)
        ref = expected[case_id]
        ensure(type(obj['study_id']) is str and obj['study_id'] == study and
               type(obj['plan_sha256']) is str and obj['plan_sha256'] == plan_digest and
               type(obj['payload_sha256']) is str and obj['payload_sha256'] == sha(ref.reference_payload) and
               type(obj['source_uri']) is str and obj['source_uri'] == ref.source_uri and
               type(obj['license_id']) is str and obj['license_id'] == ref.license_id and
               type(obj['calibration_record_ref']) is str and
               obj['calibration_record_ref'] == ref.calibration_record_ref,
               'SOURCE_SIGNATURE_BINDING_MISMATCH')
        records[case_id] = (rec.key_id, obj['observed_at_ms'])
    ensure(seen == set(expected), 'MISSING_SOURCE_SIGNATURE')
    return p4_result, records


def evaluate_p5(req: wire.T4P5ProvenanceRequest,
                policy: Mapping[str, TrustedSigner]) -> wire.T4P5ProvenanceResult:
    p4_result, records = _sources(req, policy)
    result = wire.T4P5ProvenanceResult(
        source_signatures_verified=len(records),
        trusted_policy_signatures_verified=True,
        external_publisher_identity_verified=False,
        physical_measurements_verified=False,
        research_only=True, grants_authority=False)
    result.p4_result.CopyFrom(p4_result)
    result.warnings.extend([
        'EXTERNAL_TRUST_POLICY_AND_SIGNER_IDENTITIES_NOT_INDEPENDENTLY_AUDITED',
        'SIGNATURE_DOES_NOT_ESTABLISH_LICENSE_CALIBRATION_OR_MEASUREMENT',
        'SIGNER_TIMESTAMP_IS_NOT_EXTERNAL_TIME_AUTHORITY',
        'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
    return result


def _lock(req: wire.T4P6PlanLockRequest,
          policy: Mapping[str, TrustedSigner]):
    base_contract(req, wire.T4P6PlanLockRequest, 'P6')
    ensure(req.HasField('p5') and req.HasField('plan_lock'), 'MISSING_PLAN_LOCK')
    p5_result, sources = _sources(req.p5, policy)
    obj = statement(req.plan_lock, P6_DOMAIN, 'plan_attestor',
                    {'schema_version','study_id','plan_sha256','locked_at_ms'},
                    policy, 'locked_at_ms')
    ensure(type(obj['study_id']) is str and obj['study_id'] == req.p5.p4.p3_audit.study_id and
           type(obj['plan_sha256']) is str and obj['plan_sha256'] == sha(req.p5.p4.frozen_plan_json),
           'PLAN_LOCK_BINDING_MISMATCH')
    source_keys = {s[0] for s in sources.values()}
    ensure(req.plan_lock.key_id not in source_keys and
           policy[req.plan_lock.key_id].public_key not in {policy[k].public_key for k in source_keys},
           'PLAN_ATTESTOR_NOT_SEPARATE_FROM_SOURCE')
    ensure(all(obj['locked_at_ms'] < observed_at for _, observed_at in sources.values()),
           'PLAN_NOT_LOCKED_BEFORE_OBSERVATION')
    result5 = wire.T4P5ProvenanceResult(
        source_signatures_verified=len(sources),
        trusted_policy_signatures_verified=True,
        external_publisher_identity_verified=False,
        physical_measurements_verified=False,
        research_only=True, grants_authority=False)
    result5.p4_result.CopyFrom(p5_result)
    result5.warnings.append('EXTERNAL_SOURCE_IDENTITY_NOT_ESTABLISHED')
    return result5, sources, obj['locked_at_ms']


def evaluate_p6(req: wire.T4P6PlanLockRequest,
                policy: Mapping[str, TrustedSigner]) -> wire.T4P6PlanLockResult:
    p5_result, _, _ = _lock(req, policy)
    result=wire.T4P6PlanLockResult(signed_timeline_consistent=True,
                                  independent_preregistration_verified=False,
                                  research_only=True, grants_authority=False)
    result.p5_result.CopyFrom(p5_result)
    result.warnings.extend([
        'OFFLINE_SIGNED_TIMES_CAN_BE_BACKDATED_BY_TRUSTED_SIGNERS',
        'NO_INDEPENDENT_TIME_STAMP_AUTHORITY_OR_EXTERNAL_PREREGISTRY_VALIDATED',
        'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
    return result


def evaluate_p7(req: wire.T4P7AdjudicationRequest,
                policy: Mapping[str, TrustedSigner]) -> wire.T4P7AdjudicationResult:
    base_contract(req, wire.T4P7AdjudicationRequest, 'P7')
    ensure(req.HasField('p6'), 'MISSING_REVIEW_CONTEXT')
    p5_result, sources, lock_time = _lock(req.p6, policy)
    expected = {ref.case_id: ref for ref in req.p6.p5.p4.references}
    cases = {case.case_id: case for case in req.p6.p5.p4.p3_audit.cases}
    ensure(len(req.reviewer_statements) == 2*len(expected),
           'MISSING_DUAL_REVIEW')
    result6=wire.T4P6PlanLockResult(signed_timeline_consistent=True,
                                    independent_preregistration_verified=False,
                                    research_only=True, grants_authority=False)
    result6.p5_result.CopyFrom(p5_result)
    study = req.p6.p5.p4.p3_audit.study_id
    used: dict[str, set[str]] = {case: set() for case in expected}
    used_key_material: dict[str, set[bytes]] = {case: set() for case in expected}
    source_key_material = {policy[k].public_key for k, _ in sources.values()}
    lock_key_material = policy[req.p6.plan_lock.key_id].public_key
    views: dict[str, set[str]] = {case: set() for case in expected}
    for rec in req.reviewer_statements:
        obj = statement(rec, P7_DOMAIN, 'reviewer',
                        {'schema_version','case_id','study_id','payload_sha256',
                         'observed_class','reviewed_at_ms','review_protocol_id',
                         'blind_to_model_prediction'}, policy, 'reviewed_at_ms')
        case_id = obj['case_id']
        ensure(type(case_id) is str and case_id in expected, 'UNKNOWN_REVIEW_CASE')
        ensure(rec.key_id not in used[case_id] and
               policy[rec.key_id].public_key not in used_key_material[case_id],
               'DUPLICATE_REVIEWER_FOR_CASE')
        ensure(rec.key_id != req.p6.plan_lock.key_id and
               policy[rec.key_id].public_key != lock_key_material and
               policy[rec.key_id].public_key not in source_key_material,
               'REVIEWER_NOT_ROLE_SEPARATE')
        ensure(obj['reviewed_at_ms'] > lock_time and
               obj['reviewed_at_ms'] >= sources[case_id][1],
               'REVIEW_PRECEDES_REFERENCE_OR_LOCK')
        ensure(type(obj['study_id']) is str and obj['study_id'] == study and
               type(obj['payload_sha256']) is str and
               obj['payload_sha256'] == sha(expected[case_id].reference_payload),
               'REVIEW_BINDING_MISMATCH')
        ensure(type(obj['blind_to_model_prediction']) is bool and
               obj['blind_to_model_prediction'] and
               type(obj['review_protocol_id']) is str and
               _ident(obj['review_protocol_id']), 'REVIEW_PROTOCOL_NOT_DECLARED')
        ensure(type(obj['observed_class']) is str and
               obj['observed_class'] in ('satisfies','violates','undetermined'),
               'INVALID_REVIEW_LABEL')
        used[case_id].add(rec.key_id)
        used_key_material[case_id].add(policy[rec.key_id].public_key)
        views[case_id].add(obj['observed_class'])
    labels = {1:'satisfies',2:'violates',3:'undetermined'}
    for case_id in cases:
        ensure(len(used[case_id]) == 2, 'MISSING_DUAL_REVIEW')
        ensure(len(views[case_id]) == 1, 'REVIEWER_DISAGREEMENT_REQUIRES_ADJUDICATION')
        ensure(next(iter(views[case_id])) == labels.get(cases[case_id].observed_class),
               'REVIEW_LABEL_CONTRADICTS_OBSERVATION')
    result=wire.T4P7AdjudicationResult(
        reviewed_cases=len(expected), verified_signatures=len(req.reviewer_statements),
        two_reviewer_consensus=True, actual_blinding_verified=False,
        qualified_expert_status_verified=False, licensed_real_world_data_verified=False,
        physical_safety_verified=False, research_only=True, grants_authority=False)
    result.p6_result.CopyFrom(result6)
    result.warnings.extend([
        'SIGNED_BLINDING_CLAIM_IS_NOT_AN_INDEPENDENT_BLINDING_AUDIT',
        'REVIEWER_EXPERTISE_AND_REAL_WORLD_QUALIFICATIONS_NOT_VERIFIED',
        'CONSENSUS_IS_NOT_LAB_TRUTH_OR_PHYSICAL_SAFETY_CERTIFICATION',
        'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
    return result
