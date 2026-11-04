"""C18 bounded post-hoc temperature calibration on an independent time window.

Fits SciPy scalar temperature to a frozen candidate's class probabilities
using ONLY intermediate calibration observations. Final held-out labels are
not available to the fitter. A temperature is a statistical recalibration,
not evidence of actual user authorization or trustworthy source labels.
"""
from dataclasses import dataclass,replace
from hashlib import sha256
from math import isfinite,log,exp

from .adaptation_policy import (
    Trace,AdaptationProposal,RoutingPolicy,ROUTES,
    _canonical,_digest,_predict,verify_policy,
)

@dataclass(frozen=True)
class CalibrationArtifact:
    schema_version:int
    policy_digest:str
    proposal_id:str
    calibration_digest:str
    first_calibration_ms:int
    last_calibration_ms:int
    temperature:float
    calibration_rows:int
    digest:str

@dataclass(frozen=True)
class CalibrationMetrics:
    count:int
    raw_log_loss:float
    calibrated_log_loss:float
    raw_brier:float
    calibrated_brier:float
    limitations:tuple[str,...]=(
        "calibration_on_consent_claimed_labels_not_real_truth_attestation",
        "fit_and_final_test_periods_disjoint",
        "temperature_not_an_independent_probability_guarantee",
    )

def _seal(a):
    data={name:getattr(a,name) for name in CalibrationArtifact.__dataclass_fields__
          if name!="digest"}
    return replace(a,digest=sha256(_canonical(data)).hexdigest())

def verify(a:CalibrationArtifact,policy:RoutingPolicy):
    verify_policy(policy)
    if (type(a) is not CalibrationArtifact or a.schema_version!=1
            or a.policy_digest!=policy.digest or a.proposal_id!=policy.proposal_id
            or not _digest(a.calibration_digest) or not _digest(a.digest)
            or type(a.first_calibration_ms) is not int
            or type(a.last_calibration_ms) is not int
            or a.first_calibration_ms>a.last_calibration_ms
            or type(a.calibration_rows) is not int
            or not 8<=a.calibration_rows<=128
            or type(a.temperature) not in (int,float)
            or not isfinite(a.temperature) or not .25<=a.temperature<=5
            or _seal(a).digest!=a.digest):
        raise ValueError("invalid or modified C18 calibration artifact")
    return a

def _adjust(prob,temperature):
    weights=[exp(log(max(1e-12,p))/temperature) for p in prob]
    z=sum(weights)
    return tuple(x/z for x in weights)

def _check(proposal,policy,rows,*,mode):
    verify_policy(policy)
    if (type(proposal) is not AdaptationProposal
            or policy.proposal_id!=proposal.proposal_id
            or policy.workspace_id!=proposal.workspace_id
            or policy.base_policy_digest!=proposal.base_policy_digest
            or type(rows) is not tuple or not 8<=len(rows)<=128):
        raise ValueError("calibration proposal or cohort mismatch")
    ids=set()
    last=-1
    for row in rows:
        if (type(row) is not Trace or row.event_id in ids
                or type(row.occurred_ms) is not int
                or not last<row.occurred_ms<proposal.retention_until_ms
                or row.source_digest!=proposal.source_digest
                or row.consent_receipt!=proposal.consent_receipt
                or row.task_family not in proposal.allowed_families
                or row.expected_route not in ROUTES):
            raise ValueError("untrusted or overlapping calibration cohort")
        if mode=="calibration":
            valid=proposal.train_before_ms<=row.occurred_ms<proposal.holdout_from_ms
        else:
            valid=proposal.holdout_from_ms<=row.occurred_ms
        if not valid:
            raise ValueError("chronological calibration/heldout boundary violated")
        _predict(policy,row.features)
        last=row.occurred_ms
        ids.add(row.event_id)
    return rows

def fit(proposal:AdaptationProposal,policy:RoutingPolicy,
        calibration_rows:tuple[Trace,...],*,host_authorized=False):
    if host_authorized is not True:
        raise PermissionError("calibration uses labels; independent host consent required")
    rows=_check(proposal,policy,calibration_rows,mode="calibration")
    try:
        from scipy.optimize import minimize_scalar
    except ImportError as exc:
        raise RuntimeError("scipy_calibration_backend_unavailable") from exc
    pairs=[(_predict(policy,r.features),ROUTES.index(r.expected_route)) for r in rows]
    def objective(t):
        return -sum(log(max(_adjust(probs,t)[klass],1e-12)) for probs,klass in pairs)/len(pairs)
    solution=minimize_scalar(objective,method="bounded",bounds=(.25,5),
                              options={"xatol":1e-5,"maxiter":100})
    if not solution.success or not isfinite(solution.x):
        raise RuntimeError("calibration_optimizer_failed")
    digest=sha256(_canonical([(r.event_id,r.occurred_ms,r.expected_route)
                              for r in rows])).hexdigest()
    obj=CalibrationArtifact(1,policy.digest,proposal.proposal_id,digest,
                            rows[0].occurred_ms,rows[-1].occurred_ms,
                            float(solution.x),len(rows),"")
    return verify(_seal(obj),policy)

def evaluate(proposal,policy,artifact,heldout_rows):
    verify(artifact,policy)
    rows=_check(proposal,policy,heldout_rows,mode="heldout")
    # A future-only scoring path. Never call fit using this data.
    if rows[0].occurred_ms<=artifact.last_calibration_ms:
        raise ValueError("calibration leaked into heldout")
    raw_loss=adjusted_loss=raw_brier=adjusted_brier=0.
    for row in rows:
        probs=_predict(policy,row.features)
        corrected=_adjust(probs,artifact.temperature)
        truth=ROUTES.index(row.expected_route)
        raw_loss-=log(max(1e-12,probs[truth]))
        adjusted_loss-=log(max(1e-12,corrected[truth]))
        raw_brier+=sum((p-(i==truth))**2 for i,p in enumerate(probs))
        adjusted_brier+=sum((p-(i==truth))**2 for i,p in enumerate(corrected))
    n=len(rows)
    return CalibrationMetrics(n,raw_loss/n,adjusted_loss/n,
                              raw_brier/n,adjusted_brier/n)
