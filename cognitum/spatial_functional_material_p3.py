"""C15 T4 P3: bounded, reference-labelled adversarial evaluation of T4 P2.

This is a *measurement of disagreement* between independent caller-asserted
references and P2's conditional claims. It neither authenticates the references
nor promotes the model's engineering assertions into physical safety claims.
Calibration and holdout are segregated audit partitions, not training stages.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p3_pb2 as pb
from cognitum.spatial_functional_material import T4Rejected, _ident, _no_unknown
from cognitum.spatial_functional_material_p2 import analyze as analyze_p2

_Z95 = 1.959963984540054
_MAX_CASES = 160
_MAX_WIRE_BYTES = 1_800_000


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise T4Rejected(message)


def _sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _rate(numerator: int, denominator: int) -> pb.T4P3Rate:
    result = pb.T4P3Rate(numerator=numerator, denominator=denominator)
    if denominator == 0:
        return result
    p = numerator / denominator
    z2 = _Z95 * _Z95
    d = 1 + z2 / denominator
    c = (p + z2 / (2 * denominator)) / d
    h = _Z95 * math.sqrt((p * (1 - p) + z2 / (4 * denominator)) / denominator) / d
    result.defined = True
    result.estimate = p
    result.wilson_95_low = max(0, c - h)
    result.wilson_95_high = min(1, c + h)
    return result


@dataclass(frozen=True)
class _Reference:
    partition: int
    observation: int
    prediction: int
    kind: int
    numeric_available: bool
    numeric_hit: bool


def _summary(partition: int, records: Iterable[_Reference], nominal: float) -> pb.T4P3PartitionMetrics:
    records = list(records)
    summary = pb.T4P3PartitionMetrics(partition=partition, cases=len(records))
    valid = [r for r in records if r.observation in
             (pb.T4P3_OBSERVED_SATISFIES, pb.T4P3_OBSERVED_VIOLATES)]
    summary.with_reference_class = len(valid)
    summary.reference_unknown = len(records) - len(valid)
    decided = [r for r in valid if r.prediction in
               (b.T4_CONSISTENT_WITH_CLAIMS, b.T4_CONTRADICTS_CLAIMS)]
    summary.decided = len(decided)
    summary.abstained = len(valid) - len(decided)
    summary.false_positive = sum(r.prediction == b.T4_CONSISTENT_WITH_CLAIMS and
                                 r.observation == pb.T4P3_OBSERVED_VIOLATES for r in decided)
    summary.false_negative = sum(r.prediction == b.T4_CONTRADICTS_CLAIMS and
                                 r.observation == pb.T4P3_OBSERVED_SATISFIES for r in decided)
    errors = summary.false_positive + summary.false_negative
    summary.selective_error.CopyFrom(_rate(errors, len(decided)))
    summary.false_positive_rate.CopyFrom(_rate(summary.false_positive,
        sum(r.observation == pb.T4P3_OBSERVED_VIOLATES for r in valid)))
    summary.false_negative_rate.CopyFrom(_rate(summary.false_negative,
        sum(r.observation == pb.T4P3_OBSERVED_SATISFIES for r in valid)))
    summary.decision_coverage.CopyFrom(_rate(len(decided), len(valid)))
    numeric = [r for r in records if r.numeric_available]
    summary.claimed_interval_coverage.CopyFrom(_rate(sum(r.numeric_hit for r in numeric), len(numeric)))
    summary.contains_non_synthetic_claims = any(r.kind != pb.T4P3_SYNTHETIC_ORACLE for r in records)
    summary.has_enough_cases_for_exploratory_rates = len(valid) >= 30 and len(decided) >= 20
    if nominal == 0:
        summary.nominal_coverage_audit = 'NO_PROBABILITY_COVERAGE_CLAIM'
    elif not summary.claimed_interval_coverage.defined or len(numeric) < 30:
        summary.nominal_coverage_audit = 'INSUFFICIENT_NUMERIC_SAMPLE'
    elif summary.claimed_interval_coverage.wilson_95_high < nominal:
        summary.nominal_coverage_audit = 'EMPIRICAL_COVERAGE_BELOW_CLAIM'
    elif summary.claimed_interval_coverage.wilson_95_low >= nominal:
        summary.nominal_coverage_audit = 'EMPIRICAL_COVERAGE_MEETS_CLAIM_EXPLORATORY'
    else:
        summary.nominal_coverage_audit = 'EMPIRICAL_COVERAGE_INCONCLUSIVE'
    return summary


def audit(request: pb.T4P3AuditRequest) -> pb.T4P3AuditResult:
    _require(isinstance(request, pb.T4P3AuditRequest) and
             request.schema_version == 1 and request.research_only and
             not request.grants_authority and _ident(request.study_id) and
             _ident(request.conversation_id), 'INVALID_P3_CONTRACT')
    _require(_no_unknown(request), 'UNKNOWN_PROTO_FIELDS')
    _require(len(request.prespecified_plan_sha256) == 32, 'MISSING_PLAN_IDENTITY')
    _require(1 <= len(request.cases) <= _MAX_CASES and
             len(request.SerializeToString()) <= _MAX_WIRE_BYTES, 'P3_RESOURCE_LIMIT')
    nominal = request.claimed_nominal_coverage
    _require(math.isfinite(nominal) and (nominal == 0 or .5 <= nominal < 1),
             'INVALID_NOMINAL_COVERAGE_CLAIM')
    outputs = pb.T4P3AuditResult(research_only=True,
         grants_authority=False, independent_evidence_authenticated=False,
         physical_validity_verified=False,
         request_sha256=_sha(request.SerializeToString(deterministic=True)))
    used_ids = set()
    used_specimens = set()
    used_requests = {}  # forbids leakage from calibration scenarios into holdout
    partitioned = {pb.T4P3_CALIBRATION: [], pb.T4P3_HOLDOUT: []}
    for case in sorted(request.cases, key=lambda r: r.case_id):
        _require(_ident(case.case_id) and _ident(case.specimen_group_id) and
                 _ident(case.reference_source_ref) and _ident(case.finding_id) and
                 len(case.reference_sha256) == 32, 'INVALID_REFERENCE_IDENTITY')
        _require(case.case_id not in used_ids, 'DUPLICATE_CASE_ID')
        _require(case.specimen_group_id not in used_specimens,
                 'DEPENDENT_OR_DUPLICATE_SPECIMEN')
        used_ids.add(case.case_id)
        used_specimens.add(case.specimen_group_id)
        _require(case.partition in partitioned, 'UNKNOWN_EVALUATION_PARTITION')
        _require(case.reference_kind in (pb.T4P3_SYNTHETIC_ORACLE,
                    pb.T4P3_PUBLISHED_REFERENCE_CLAIM,
                    pb.T4P3_LAB_OBSERVATION_CLAIM), 'UNKNOWN_REFERENCE_PROVENANCE')
        _require(case.observed_class in (pb.T4P3_OBSERVED_SATISFIES,
                    pb.T4P3_OBSERVED_VIOLATES,
                    pb.T4P3_OBSERVED_UNDETERMINED), 'UNKNOWN_REFERENCE_CLASS')
        _require(case.scenario.baseline.conversation_id == request.conversation_id,
                 'CROSS_CONVERSATION_EVIDENCE')
        fingerprint = _sha(case.scenario.SerializeToString(deterministic=True))
        _require(fingerprint not in used_requests or used_requests[fingerprint] == case.partition,
                 'CALIBRATION_HOLDOUT_SCENARIO_LEAK')
        used_requests[fingerprint] = case.partition
        result = analyze_p2(case.scenario)  # independently execute the P2 research kernel
        matching = [x for x in result.findings if x.id == case.finding_id]
        _require(len(matching) == 1, 'MISSING_OR_DUPLICATE_P2_FINDING')
        finding = matching[0]
        _require(case.reference_source_ref not in finding.source_refs,
                 'REFERENCE_REUSED_AS_MODEL_INPUT')
        _require(finding.status in (b.T4_CONSISTENT_WITH_CLAIMS,
                  b.T4_CONTRADICTS_CLAIMS, b.T4_UNDETERMINED), 'INVALID_P2_STATUS')
        finding_is_fit = finding.conditional_model == 'TOLERANCED_BORE_SHAFT_CLEARANCE_SI'
        _require(not case.HasField('observed_clearance_m') or finding_is_fit,
                 'NUMERIC_REFERENCE_WRONG_DIMENSION')
        observed_numeric = case.HasField('observed_clearance_m')
        numeric_hit = False
        if observed_numeric:
            observed = case.observed_clearance_m
            _require(math.isfinite(observed), 'NONFINITE_REFERENCE_OBSERVATION')
            _require(math.isfinite(finding.computed_min_si) and
                     math.isfinite(finding.computed_max_si) and
                     finding.computed_min_si <= finding.computed_max_si and
                     bool(set(finding.reasons) & {
                         'ROBUST_WITHIN_CALLER_ASSERTED_INTERVALS',
                         'INTERVAL_OVERLAP_OR_PROVISIONAL_EVIDENCE',
                         'ALL_REALIZATIONS_OUTSIDE_SUPPLIED_BOUNDS'}),
                     'NO_VALID_PREDICTED_INTERVAL')
            numeric_hit = finding.computed_min_si <= observed <= finding.computed_max_si
        predicted = finding.status
        falsified_label = (predicted == b.T4_CONSISTENT_WITH_CLAIMS and
                           case.observed_class == pb.T4P3_OBSERVED_VIOLATES) or (
                           predicted == b.T4_CONTRADICTS_CLAIMS and
                           case.observed_class == pb.T4P3_OBSERVED_SATISFIES)
        item = outputs.audited_cases.add(case_id=case.case_id, partition=case.partition,
            observed_class=case.observed_class, predicted_status=predicted,
            label_falsifies_decision=falsified_label,
            numeric_reference_available=observed_numeric,
            claimed_interval_contains_reference=numeric_hit if observed_numeric else False,
            claimed_interval_falsified=observed_numeric and not numeric_hit)
        if falsified_label:
            item.reason_codes.append('REFERENCE_CONTRADICTS_CONDITIONAL_DECISION')
        if observed_numeric and not numeric_hit:
            item.reason_codes.append('REFERENCE_OUTSIDE_CALLER_ASSERTED_INTERVAL')
        if predicted == b.T4_UNDETERMINED:
            item.reason_codes.append('P2_ABSTAINED')
        if case.observed_class == pb.T4P3_OBSERVED_UNDETERMINED:
            item.reason_codes.append('REFERENCE_CLASS_UNDETERMINED')
        if case.reference_kind == pb.T4P3_SYNTHETIC_ORACLE:
            item.reason_codes.append('SYNTHETIC_ONLY')
        partitioned[case.partition].append(_Reference(case.partition,case.observed_class,
            predicted,case.reference_kind,observed_numeric,numeric_hit))
    outputs.calibration.CopyFrom(_summary(pb.T4P3_CALIBRATION,
        partitioned[pb.T4P3_CALIBRATION],nominal))
    outputs.holdout.CopyFrom(_summary(pb.T4P3_HOLDOUT,
        partitioned[pb.T4P3_HOLDOUT],nominal))
    outputs.warnings.extend((
        'REFERENCE_SOURCE_AND_SHA256_UNAUTHENTICATED',
        'SYNTHETIC_HELDOUT_IS_NOT_REAL_ENGINEERING_VALIDATION',
        'WILSON_95_ASSUMES_INDEPENDENT_BINOMIAL_OBSERVATIONS',
        'SPECIMEN_UNIQUENESS_IS_ONLY_CLAIMED_NOT_PROVEN',
        'P2_BOUNDS_ARE_NOT_PROBABILISTIC_COVERAGE_INTERVALS',
        'CALIBRATION_PARTITION_IS_AUDIT_ONLY_NO_MODEL_FITTING',
        'CONDITIONAL_DECISION_DISAGREEMENT_NOT_VERIFIED_PHYSICAL_HAZARD',
        'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY',
    ))
    return outputs
