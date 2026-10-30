"""G12 synthetic stress report admission, not causal proof or action permission.

Checks pinned G11 request/decision/receipt, a frozen G12 report digest, and
independent numeric recomputation. Distinct synthetic mechanisms deliberately
make old calibration inapplicable. All causal generalization is abstained.
"""
import hashlib
import json
from pathlib import Path
from cognitum import causal_holdout_assurance as g11
from cognitum import causal_g12_independent_verifier as independent
from cognitum.proto import causal_adversarial_assurance_pb2 as pb

REPORT_PATH=Path(__file__).resolve().parents[1]/'docs/components/causal/P4E-G12-adversarial-mechanisms-evidence.json'
PINNED_G12_REPORT_SHA256='9ebe4f80ac40d6f1dcd1740ca4f23b41f9be3edd0b3d25f09e80be621d96f51d'
PINNED_G11_SOURCE_SHA256='1c88ce5573796eca7a29ba56c7d13b35158ddad15d51818fab27c5c7169c2668'
ADVERSARIAL=('HIDDEN_COMMON_CAUSE','MISMEASURED_CONFOUNDER','SELECTION_COLLIDER','TRANSPORT_SHIFT')


def _sha(v):
    return hashlib.sha256(v.SerializeToString(deterministic=True)).digest()


def _load_report():
    if hashlib.sha256(Path(g11.__file__).read_bytes()).hexdigest()!=PINNED_G11_SOURCE_SHA256:
        raise ValueError('G11_SOURCE_CHANGED')
    raw=REPORT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINNED_G12_REPORT_SHA256:
        raise ValueError('UNAPPROVED_G12_REPORT')
    report=json.loads(raw)
    check=independent.verify_report(report)
    if check['records_verified']!=960 or check['causal_assumptions_proven'] or check['real_world_authority']:
        raise ValueError('G12_INDEPENDENT_REVIEW_FAILED')
    return report


def _seal(req,d):
    return d,pb.AdversarialAssuranceReceipt(request_sha256=_sha(req),decision_sha256=_sha(d),
        pinned_study_sha256=d.pinned_study_sha256,
        independent_arithmetic_replayed=d.independent_evidence_math_verified,authenticated_lu_host=False)


def calculate(req):
    if (not isinstance(req,pb.AdversarialAssuranceRequest) or req.schema_version!=1
        or not 1<=len(req.trace_id)<=128 or not req.HasField('upstream_request')
        or not req.HasField('upstream_decision') or not req.HasField('upstream_receipt')):
        raise ValueError('INVALID_G12_TYPED_REQUEST')
    d=pb.AdversarialAssuranceDecision(schema_version=1,trace_id=req.trace_id,request_sha256=_sha(req),
        disposition='REJECT_UNVERIFIED',research_only=True,
        machine_safe_summary='Reject: evidence could not be independently verified. No causal claim or action.')
    if not g11.verify(req.upstream_request,req.upstream_decision,req.upstream_receipt):
        d.reason_codes.append('UPSTREAM_G11_REPLAY_FAILED');return _seal(req,d)
    d.upstream_replay_checked=True
    try:
        report=_load_report()
        key=f'{req.study_scenario}@{req.study_sample_size}'
        entry=report['summary'][key]
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError,ZeroDivisionError):
        d.reason_codes.append('FROZEN_G12_EVIDENCE_NOT_VERIFIED_OR_CASE_UNSUPPORTED');return _seal(req,d)
    d.pinned_study_sha256=bytes.fromhex(PINNED_G12_REPORT_SHA256)
    d.independent_evidence_math_verified=True
    d.studied_datasets=entry['attempts']
    d.naive_mean_absolute_error=entry['mean_absolute_naive_error']
    d.adjusted_mean_absolute_error=entry['mean_absolute_stratified_error']
    d.assumption_violation_known_from_synthetic_generator=req.study_scenario in ADVERSARIAL
    d.reason_codes.extend(('DIFFERENT_GENERATOR_FROM_G9_G11_CALIBRATION',
        'ARITHMETIC_VERIFIED_NOT_CAUSAL_GRAPH_OR_GENERATOR_AUTHENTICATION',
        'NO_EXTERNAL_ACTION_AUTHORITY'))
    if req.requests_intervention_recommendation:
        d.reason_codes.append('REQUESTED_INTERVENTION_NEVER_AUTHORIZED')
    if req.upstream_decision.disposition in ('ABSTAIN_HOLDOUT_CALIBRATION','ABSTAIN_UPSTREAM_G10'):
        d.disposition='ABSTAIN_UPSTREAM'
        d.reason_codes.append('NO_UPGRADE_FROM_UPSTREAM_ABSTENTION')
    elif not (req.upstream_decision.disposition=='DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY'
              and req.upstream_request.declared_evaluation_domain==g11.KNOWN_SYNTHETIC_DOMAIN):
        d.disposition='ABSTAIN_UPSTREAM'
        d.reason_codes.append('NO_UPGRADE_FROM_UNSUPPORTED_UPSTREAM_DOMAIN')
    elif d.assumption_violation_known_from_synthetic_generator:
        d.disposition='ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION'
        d.reason_codes.append('KNOWN_ADVERSARIAL_IDENTIFICATION_OR_TRANSPORT_RISK')
    else:
        d.disposition='ABSTAIN_NEW_UNCALIBRATED_GENERATOR'
        d.reason_codes.append('INDEPENDENT_NEW_GENERATOR_NOT_G10_G11_CALIBRATED')
    # Bounded reporting of these synthetic failure diagnostics is not a license
    # to reuse a G11 interval, assert causality, or make a real-world recommendation.
    d.may_describe_synthetic_stress_diagnostic=(d.disposition != 'ABSTAIN_UPSTREAM')
    d.machine_safe_summary=('Only a qualified *synthetic stress-test* diagnostic may be reported. '
        'The original causal estimate is NOT externally validated; no action authorized.')
    return _seal(req,d)


def verify(req,d,receipt):
    if not (isinstance(req,pb.AdversarialAssuranceRequest) and isinstance(d,pb.AdversarialAssuranceDecision)
        and isinstance(receipt,pb.AdversarialAssuranceReceipt)):
        return False
    if (not d.research_only or d.may_issue_real_world_causal_claim or d.may_recommend_intervention
        or d.may_trigger_external_action or d.authenticated_lu_host or receipt.authenticated_lu_host):
        return False
    try:
        expected,token=calculate(req)
        return (d.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)
            and receipt.SerializeToString(deterministic=True)==token.SerializeToString(deterministic=True))
    except (ValueError,TypeError,KeyError,OSError,ZeroDivisionError):
        return False
