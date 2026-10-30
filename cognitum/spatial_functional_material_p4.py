"""C15 T4 P4: fail-closed content integrity and split-locked P3 evaluation.

The caller supplies all bytes, including the plan and reference observations.
Hash equality alone cannot prove a measurement is real, independent, correctly
licensed, calibrated or timestamped. No IO, URL fetching, secret handling,
physical action, user authority, or integration with Lu occurs here.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.proto import spatial_functional_material_p4_pb2 as p4
from cognitum.spatial_functional_material import T4Rejected, _no_unknown, _ident
from cognitum.spatial_functional_material_p3 import audit as p3_audit

_MAX_CASES = 160
_MAX_REQUEST_BYTES = 3_000_000
_MAX_REFERENCE_BYTES = 8192
_MAX_PLAN_BYTES = 32768


def _fail(code: str) -> None:
    raise T4Rejected(code)


def _ensure(condition: bool, code: str) -> None:
    if not condition:
        _fail(code)


def _sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _parse(raw: bytes, limit: int, code: str) -> dict[str, Any]:
    _ensure(0 < len(raw) <= limit, code)
    try:
        obj = json.loads(raw.decode('utf-8', errors='strict'),
                         object_pairs_hook=_pairs_no_duplicates,
                         parse_constant=lambda _: _fail('NONFINITE_JSON_VALUE'))
    except T4Rejected:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise T4Rejected(code) from exc
    _ensure(isinstance(obj, dict), code)
    return obj


def _strict_keys(obj: dict, required: set[str], optional: set[str] = frozenset()) -> None:
    _ensure(required <= set(obj) and not set(obj) - (required | optional), 'UNEXPECTED_OR_MISSING_JSON_FIELD')


def _partition(value: Any) -> int:
    if value == 'calibration':
        return p3.T4P3_CALIBRATION
    if value == 'holdout':
        return p3.T4P3_HOLDOUT
    _fail('INVALID_FROZEN_PARTITION')


def evaluate(request: p4.T4P4EvidenceRequest) -> p4.T4P4EvidenceResult:
    _ensure(isinstance(request, p4.T4P4EvidenceRequest), 'INVALID_P4_CONTRACT')
    _ensure(request.schema_version == 1 and request.research_only and not request.grants_authority,
            'INVALID_P4_CONTRACT')
    _ensure(_no_unknown(request), 'UNKNOWN_PROTO_FIELDS')
    _ensure(request.HasField('p3_audit') and request.p3_audit.schema_version == 1 and
            request.p3_audit.research_only and not request.p3_audit.grants_authority,
            'INVALID_P3_CONTRACT')
    _ensure(len(request.SerializeToString()) <= _MAX_REQUEST_BYTES and
            1 <= len(request.references) <= _MAX_CASES and
            len(request.references) == len(request.p3_audit.cases), 'P4_RESOURCE_LIMIT')

    # Plan is fully content-addressed, but is NOT externally time-locked.
    plan = _parse(request.frozen_plan_json, _MAX_PLAN_BYTES, 'INVALID_FROZEN_PLAN')
    _strict_keys(plan, {'plan_version','study_id','conversation_id','model_id',
                        'case_partitions','reference_format'})
    _ensure(type(plan['plan_version']) is int and plan['plan_version'] == 1 and plan['model_id'] == 'C15_T4_P2' and
            plan['reference_format'] == 'C15_T4_P4_OBSERVATION_V1' and
            type(plan['study_id']) is str and type(plan['conversation_id']) is str and
            plan['study_id'] == request.p3_audit.study_id and
            plan['conversation_id'] == request.p3_audit.conversation_id and
            isinstance(plan['case_partitions'], dict) and
            len(plan['case_partitions']) == len(request.p3_audit.cases),
            'FROZEN_PLAN_MISMATCH')
    _ensure(_sha(request.frozen_plan_json) == request.p3_audit.prespecified_plan_sha256,
            'FROZEN_PLAN_SHA256_MISMATCH')
    groups: dict[str, str] = {}
    for case in request.p3_audit.cases:
        _ensure(_ident(case.case_id) and _ident(case.specimen_group_id), 'INVALID_CASE_IDENTITY')
        _ensure(case.case_id not in groups, 'DUPLICATE_CASE_ID')
        groups[case.case_id] = case.specimen_group_id
        _ensure(case.case_id in plan['case_partitions'] and
                _partition(plan['case_partitions'][case.case_id]) == case.partition,
                'PLAN_PARTITION_MISMATCH')
    _ensure(set(plan['case_partitions']) == set(groups), 'EXTRA_PLAN_CASE')

    supplied_cases = {c.case_id: c for c in request.p3_audit.cases}
    outputs = p4.T4P4EvidenceResult(research_only=True, grants_authority=False,
           payload_integrity_verified=False, source_authenticity_verified=False,
           preregistration_verified=False, independent_measurement_verified=False,
           request_sha256=_sha(request.SerializeToString(deterministic=True)),
           plan_sha256=_sha(request.frozen_plan_json))
    receipts = set()
    uri_partitions: dict[str,int] = {}
    for ref in sorted(request.references, key=lambda x: x.case_id):
        _ensure(_ident(ref.case_id) and ref.case_id in supplied_cases,
                'UNEXPECTED_REFERENCE_CASE')
        _ensure(ref.case_id not in receipts, 'DUPLICATE_REFERENCE_CASE')
        receipts.add(ref.case_id)
        case = supplied_cases[ref.case_id]
        _ensure(_ident(ref.source_uri) and _ident(ref.license_id) and
                ref.license_id != 'UNSPECIFIED', 'MISSING_CLAIMED_SOURCE_OR_LICENSE')
        _ensure(ref.source_uri == case.reference_source_ref,
                'REFERENCE_URI_MISMATCH')
        if ref.source_uri in uri_partitions:
            _ensure(uri_partitions[ref.source_uri] == case.partition,
                    'REFERENCE_REUSED_ACROSS_PARTITIONS')
        uri_partitions[ref.source_uri] = case.partition
        raw = ref.reference_payload
        _ensure(len(raw) <= _MAX_REFERENCE_BYTES, 'REFERENCE_PAYLOAD_TOO_LARGE')
        digest = _sha(raw)
        _ensure(digest == case.reference_sha256, 'REFERENCE_CONTENT_HASH_MISMATCH')
        observation = _parse(raw, _MAX_REFERENCE_BYTES, 'INVALID_REFERENCE_PAYLOAD')
        _strict_keys(observation, {'schema_version','case_id','specimen_group_id',
                                  'observed_class','partition','unit'},
                     {'observed_clearance_m'})
        _ensure(type(observation['schema_version']) is int and observation['schema_version'] == 1 and
                type(observation['case_id']) is str and observation['case_id'] == ref.case_id and
                type(observation['specimen_group_id']) is str and
                observation['specimen_group_id'] == case.specimen_group_id and
                _partition(observation['partition']) == case.partition,
                'OBSERVATION_IDENTITY_MISMATCH')
        code = observation['observed_class']
        _ensure(type(code) is str, 'OBSERVED_LABEL_MISMATCH')
        label = {'satisfies':p3.T4P3_OBSERVED_SATISFIES,
                 'violates':p3.T4P3_OBSERVED_VIOLATES,
                 'undetermined':p3.T4P3_OBSERVED_UNDETERMINED}.get(code)
        _ensure(label is not None and label == case.observed_class,
                'OBSERVED_LABEL_MISMATCH')
        numeric = 'observed_clearance_m' in observation
        _ensure(observation['unit'] == ('m' if numeric else 'not_applicable'),
                'REFERENCE_UNIT_MISMATCH')
        _ensure(numeric == case.HasField('observed_clearance_m'),
                'REFERENCE_NUMERIC_PRESENCE_MISMATCH')
        if numeric:
            value = observation['observed_clearance_m']
            _ensure(type(value) in (int,float) and math.isfinite(value) and
                    float(value).hex() == case.observed_clearance_m.hex(),
                    'OBSERVATION_NUMERIC_MISMATCH')
        if case.reference_kind == p3.T4P3_LAB_OBSERVATION_CLAIM:
            _ensure(_ident(ref.calibration_record_ref), 'MISSING_CALIBRATION_CLAIM')
        outputs.verified.add(case_id=ref.case_id,verified_payload_sha256=digest,
                             content_matches_claim=True, partition_matches_plan=True)
    _ensure(receipts == set(groups), 'INCOMPLETE_REFERENCE_SET')
    # The full existing P3 evaluator enforces case/group uniqueness, split
    # isolation of scenarios, dimensional validity, and error-rate summaries.
    outputs.p3_result.CopyFrom(p3_audit(request.p3_audit))
    outputs.payload_integrity_verified = True
    outputs.warnings.extend([
        'PAYLOAD_HASH_MATCH_IS_NOT_EXTERNAL_SOURCE_AUTHENTICATION',
        'PLAN_DIGEST_IS_NOT_INDEPENDENT_PREREGISTRATION_PROOF',
        'CLAIMED_LICENSE_AND_CALIBRATION_NOT_INDEPENDENTLY_VERIFIED',
        'INDEPENDENT_LAB_MEASUREMENT_AND_EXPERT_REVIEW_UNVERIFIED',
        'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY',
    ])
    return outputs
