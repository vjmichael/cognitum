"""G11 supplemental *research-only* assurance gate on independent synthetic holdout.

This is NOT an admission layer for real datasets, a trustworthy drift detector,
a validity certificate for causal assumptions, or permission to perform actions.
G10 remains byte-for-byte frozen; decisions can only stay the same or downgrade.
"""
import hashlib
import json
from pathlib import Path
from cognitum import causal_assurance_policy as g10
from cognitum.proto import causal_holdout_assurance_pb2 as pb
from cognitum.proto import causal_assurance_policy_pb2 as ap

REPORT_PATH = (Path(__file__).resolve().parents[1]/'docs/components/causal/P4E-G11-holdout-evidence.json')
PINNED_G11_SHA256='d9df3b0dd7ba3fb9f86c60f18c8ea7974ad61db9112e021539af302b97ef919e'
FROZEN_G10_SHA256='be0301129cb6060bb157a23744262dee9018b3c622e4285c546aea420d5cfd7c'
KNOWN_SYNTHETIC_DOMAIN='FROZEN_SYNTHETIC_HOLDOUT'


def sha(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()


def _load():
    raw=REPORT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINNED_G11_SHA256:
        raise ValueError('HOLDOUT_REPORT_TAMPERED_OR_UNAPPROVED')
    report=json.loads(raw)
    design=report['design']
    if (report['phase']!='C14 P4E G11' or report['status']!='OFFLINE_SYNTHETIC_RESEARCH_ONLY'
        or report['frozen_G9_calibration_sha256']!=g10.G9_EVIDENCE_SHA256
        or report['frozen_G10_policy_sha256']!=FROZEN_G10_SHA256
        or design['holdout_seeds']!=list(range(51001,51201))
        or design['shift_seeds']!=list(range(61001,61101))
        or design['g9_training_calibration_seeds']!=list(range(2001,2201))
        or design['resamples']!=399 or design['confidence']!=.95
        or report['counts']!={'holdout_datasets':2000,'shifted_datasets':600}
        or report['claims']!={'causal_identification_proven':False,'Lu_host_authorized':False,
            'intervention_authorized':False,'real_world_calibration_certified':False,
            'windows_security_attested':False,'research_only':True}):
        raise ValueError('HOLDOUT_REPORT_INVALID_DESIGN')
    source=Path(g10.__file__).read_bytes()
    if hashlib.sha256(source).hexdigest()!=FROZEN_G10_SHA256:
        raise ValueError('UPSTREAM_POLICY_CHANGED')
    return report


def calculate(req):
    if not isinstance(req,pb.HoldoutAssuranceRequest) or req.schema_version!=1 or not 1<=len(req.trace_id)<=128 or not (req.HasField('upstream_request') and req.HasField('upstream_decision') and req.HasField('upstream_receipt')):
        raise ValueError('INVALID_TYPED_HOLDOUT_REQUEST')
    d=pb.HoldoutAssuranceDecision(schema_version=1,trace_id=req.trace_id,request_sha256=sha(req),
      research_only=True,disposition='REJECT_UNVERIFIED',
      machine_safe_summary='Reject: G11 holdout evidence not verified; never authorize causal claims or actions.')
    if not g10.verify(req.upstream_request,req.upstream_decision,req.upstream_receipt):
        d.reason_codes.append('UPSTREAM_G10_REPLAY_FAILED')
        return _seal(req,d)
    d.previous_policy_replay_checked=True
    try:
        report=_load()
        scenario=req.upstream_request.experiment.scenario
        n=req.upstream_request.experiment.sample_size
        method=req.upstream_request.selected_method
        metrics=report['holdout_summary'][f'{scenario}@{n}'][method]
    except (OSError,ValueError,KeyError,TypeError,IndexError,json.JSONDecodeError):
        d.reason_codes.append('FROZEN_HOLDOUT_REPORT_UNAVAILABLE_OR_INVALID')
        return _seal(req,d)
    d.fixed_holdout_report_sha256=bytes.fromhex(PINNED_G11_SHA256)
    d.holdout_attempts=metrics['attempts'];d.holdout_completed=metrics['computed']
    if metrics['empirical_coverage'] is not None:
        d.recorded_holdout_coverage=True;d.holdout_empirical_coverage=metrics['empirical_coverage']
        d.holdout_wilson_lower,d.holdout_wilson_upper=metrics['coverage_wilson_95']
    baseline=ap.CausalAssuranceDisposition.Name(req.upstream_decision.disposition)
    if req.declared_evaluation_domain!=KNOWN_SYNTHETIC_DOMAIN:
        d.disposition='ABSTAIN_DISTRIBUTION_UNKNOWN_OR_SHIFTED'
        d.reason_codes.append('DECLARED_DOMAIN_NOT_FIXED_G9_GENERATOR')
    elif baseline!='CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY':
        d.disposition='ABSTAIN_UPSTREAM_G10'
        d.reason_codes.append('NO_UPGRADE_OF_G10_DISPOSITION')
    else:
        expected=metrics['G11_disposition']
        if expected=='DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY':
            # independently enforce rules; don't trust the report's disposition label
            if not (metrics['causal_coverage_eligible'] and metrics['computed']>=g10.MIN_COMPLETED
                and metrics['computed']/metrics['attempts']>=g10.MIN_COMPLETION_FRACTION
                and metrics['empirical_coverage']>=.95-g10.CALIBRATION_TOLERANCE):
                d.reason_codes.append('HOLDOUT_METRIC_AND_DISPOSITION_CONTRADICT');return _seal(req,d)
            d.disposition='DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY'
            d.reason_codes.append('INDEPENDENT_SYNTHETIC_COVERAGE_POINT_THRESHOLD_MET')
        else:
            d.disposition='ABSTAIN_HOLDOUT_CALIBRATION'
            d.reason_codes.append('FROZEN_HOLDOUT_METHOD_NOT_ELIGIBLE')
    if d.recorded_holdout_coverage and d.holdout_wilson_lower < .95-g10.CALIBRATION_TOLERANCE:
        d.reason_codes.append('WILSON_LOWER_BOUND_BELOW_PRELIMINARY_THRESHOLD')
    d.reason_codes.extend(('CAUSAL_ASSUMPTIONS_NOT_INDEPENDENTLY_VERIFIED',
        'UNTRUSTED_DOMAIN_METADATA_CANNOT_ATTEST_REAL_WORLD_DATA',
        'NO_LU_HOST_OR_INTERVENTION_AUTHORITY'))
    d.machine_safe_summary={
        'DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY':'Qualified synthetic research description ONLY; not causal proof or advice to intervene.',
        'ABSTAIN_DISTRIBUTION_UNKNOWN_OR_SHIFTED':'Abstain: out of the frozen synthetic calibration domain.',
        'ABSTAIN_UPSTREAM_G10':'Abstain: upstream assurance did not approve even synthetic description.',
        'ABSTAIN_HOLDOUT_CALIBRATION':'Abstain: independent synthetic holdout does not meet preliminary descriptive criteria.'
    }[d.disposition]
    return _seal(req,d)


def _seal(req,d):
    return d,pb.HoldoutAssuranceReceipt(request_sha256=sha(req),result_sha256=sha(d),
       deterministic_replay_checked=True,authenticated_lu_host=False)


def verify(req,decision,receipt):
    if not (isinstance(req,pb.HoldoutAssuranceRequest) and isinstance(decision,pb.HoldoutAssuranceDecision)
        and isinstance(receipt,pb.HoldoutAssuranceReceipt)):
        return False
    if (not decision.research_only or decision.may_issue_real_world_causal_claim or
        decision.may_recommend_intervention or decision.may_trigger_external_action or
        decision.authenticated_lu_host or receipt.authenticated_lu_host):
        return False
    try:
        a,b=calculate(req)
        return (decision.SerializeToString(deterministic=True)==a.SerializeToString(deterministic=True)
          and receipt.SerializeToString(deterministic=True)==b.SerializeToString(deterministic=True))
    except (TypeError,ValueError,KeyError,OSError,ZeroDivisionError):
        return False
