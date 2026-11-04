"""C13 canonical Protobuf statistical specialist interface.

Never interpret probability numbers as authenticated source evidence, host
permissions, clinical decisions, or causal effects.
"""
from hashlib import sha256
from google.protobuf.message import DecodeError
from .proto import probability_pb2 as pb
from .probability_bayes import BayesProblem,Observation,infer,validate as validate_bayes
from .probability_calibration import (
    BetaProblem,CalibrationProblem,beta_posterior,calibration_scores,
)

MAX_REQUEST=1024*1024
MAX_RESULT=8192
KINDS={
    "bayes":(pb.BayesRequest,pb.BayesResult),
    "beta":(pb.BetaRequest,pb.BetaResult),
    "calibration":(pb.CalibrationRequest,pb.CalibrationResult),
}


def _parse(frame,cls,maximum):
    if type(frame) is not bytes or not 0<len(frame)<=maximum:
        raise ValueError("invalid probability wire size")
    obj=cls()
    try:
        obj.ParseFromString(frame)
    except DecodeError as exc:
        raise ValueError("invalid probability Protobuf wire") from exc
    known=cls()
    known.CopyFrom(obj)
    known.DiscardUnknownFields()
    if obj!=known or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("unknown, repeated, or noncanonical probability wire")
    return obj


def _write(obj):
    frame=obj.SerializeToString(deterministic=True)
    if not 0<len(frame)<=MAX_RESULT:
        raise ValueError("oversized probability result")
    return frame


def _bayes(req):
    if req.schema_version!=1:
        raise ValueError("unsupported Bayesian schema")
    return validate_bayes(BayesProblem(
        tuple(req.hypotheses),tuple(req.prior),
        tuple(Observation(e.name,tuple(e.likelihood_by_hypothesis),e.observed)
              for e in req.observations),
        req.prior_source,req.likelihood_source,tuple(req.assumptions),
    ))


def _beta(req):
    if req.schema_version!=1:
        raise ValueError("unsupported beta schema")
    return BetaProblem(req.successes,req.failures,req.alpha_prior,req.beta_prior,
                       req.credibility,req.prior_source,req.data_source)


def _calibration(req):
    if req.schema_version!=1:
        raise ValueError("unsupported calibration schema")
    return CalibrationProblem(tuple(req.probabilities),tuple(req.labels),
                              req.source,req.bins)


def execute(kind: str, frame: bytes) -> bytes:
    if kind not in KINDS:
        raise ValueError("unknown probability domain")
    req=_parse(frame,KINDS[kind][0],MAX_REQUEST)
    digest=sha256(frame).hexdigest()
    if kind=="bayes":
        r=infer(_bayes(req))
        res=pb.BayesResult(schema_version=1,status=r.status,method=r.method,
                           limitations=r.limitations,request_sha256=digest)
        if r.status=="OK":
            res.posterior.extend(r.posterior)
            res.evidence_probability=r.evidence_probability
            res.log_evidence=r.log_evidence
    elif kind=="beta":
        r=beta_posterior(_beta(req))
        res=pb.BetaResult(schema_version=1,status=r.status,
                          limitations=r.limitations,request_sha256=digest)
        if r.status=="OK":
            res.posterior_mean=r.posterior_mean
            res.credible_lower=r.credible_lower
            res.credible_upper=r.credible_upper
            res.alpha_posterior=r.alpha_posterior
            res.beta_posterior=r.beta_posterior
    else:
        r=calibration_scores(_calibration(req))
        res=pb.CalibrationResult(schema_version=1,status="OK",
                    brier=r.brier,log_loss=r.log_loss,
                    expected_calibration_error=r.expected_calibration_error,
                    count=r.count,bins_with_data=r.bins_with_data,
                    limitations=r.limitations,request_sha256=digest)
    return _write(res)


def decode_result(kind: str, request: bytes, response: bytes):
    if kind not in KINDS:
        raise ValueError("unknown probability domain")
    req=_parse(request,KINDS[kind][0],MAX_REQUEST)
    obj=_parse(response,KINDS[kind][1],MAX_RESULT)
    if obj.schema_version!=1 or obj.request_sha256!=sha256(request).hexdigest():
        raise ValueError("mismatched statistical response")
    # Recompute all numerical claims from the original typed inputs. This does
    # not authenticate the provenance of caller-declared data or assumptions.
    from math import isfinite
    if kind=="bayes":
        _bayes(req)
        if obj.status=="OK":
            if (len(obj.posterior)!=len(req.hypotheses)
                    or any(not isfinite(x) or x<0 or x>1 for x in obj.posterior)
                    or abs(sum(obj.posterior)-1)>1e-9
                    or not isfinite(obj.log_evidence)
                    or not isfinite(obj.evidence_probability)
                    or not 0<=obj.evidence_probability<=1):
                raise ValueError("invalid posterior")
            expected=infer(_bayes(req))
            if (expected.status!="OK"
                    or any(abs(a-b)>1e-10 for a,b in zip(obj.posterior,expected.posterior))
                    or abs(obj.log_evidence-expected.log_evidence)>1e-9
                    or abs(obj.evidence_probability-expected.evidence_probability)>1e-10):
                raise ValueError("posterior differs from independently recomputed inputs")
        elif obj.status not in ("IMPOSSIBLE_EVIDENCE","UNSUPPORTED","NUMERICAL_FAILURE") or obj.posterior:
            raise ValueError("invalid nonposterior response")
    elif kind=="beta":
        _beta(req)
        if obj.status=="OK":
            if (not all(isfinite(x) for x in (obj.posterior_mean,obj.credible_lower,obj.credible_upper))
                    or not 0<=obj.credible_lower<=obj.posterior_mean<=obj.credible_upper<=1):
                raise ValueError("invalid credible interval")
            expected=beta_posterior(_beta(req))
            if (expected.status!="OK" or any(abs(a-b)>1e-10 for a,b in (
                    (obj.posterior_mean,expected.posterior_mean),
                    (obj.credible_lower,expected.credible_lower),
                    (obj.credible_upper,expected.credible_upper),
                    (obj.alpha_posterior,expected.alpha_posterior),
                    (obj.beta_posterior,expected.beta_posterior)))):
                raise ValueError("credible interval differs from recomputed inputs")
        elif obj.status not in ("UNSUPPORTED","NUMERICAL_FAILURE"):
            raise ValueError("unknown beta status")
    else:
        _calibration(req)
        if (obj.status!="OK" or obj.count!=len(req.labels)
                or any(not isfinite(x) or x<0 for x in (obj.brier,obj.log_loss,
                                                         obj.expected_calibration_error))
                or obj.brier>1 or obj.expected_calibration_error>1):
            raise ValueError("invalid calibration scores")
        expected=calibration_scores(_calibration(req))
        if (abs(obj.brier-expected.brier)>1e-10
                or abs(obj.log_loss-expected.log_loss)>1e-10
                or abs(obj.expected_calibration_error-expected.expected_calibration_error)>1e-10
                or obj.bins_with_data!=expected.bins_with_data):
            raise ValueError("calibration differs from recomputed labels")
    return obj
