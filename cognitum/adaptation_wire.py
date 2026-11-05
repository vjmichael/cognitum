"""C18 canonical read-only Protobuf evaluation, never grants training.

Candidate and fallback checkpoints are evaluated against held-out labels,
then the result is independently recomputed. A passing evaluation is not
permission to activate a route or write a policy to Lu.
"""
from hashlib import sha256
from google.protobuf.message import DecodeError
from .proto import adaptation_pb2 as pb
from .adaptation_policy import AdaptationProposal,RoutingPolicy,Trace,verify_policy
from .adaptation_lifecycle import evaluate_promotion

MAX_INPUT=200000
MAX_RESULT=8192

def _read(frame,cls,bound):
    if type(frame) is not bytes or not 0<len(frame)<=bound:
        raise ValueError("invalid adaptation protobuf frame")
    obj=cls()
    try:obj.ParseFromString(frame)
    except DecodeError as exc:raise ValueError("malformed adaptation protobuf") from exc
    clean=cls();clean.CopyFrom(obj);clean.DiscardUnknownFields()
    if clean!=obj or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("unknown/duplicated/noncanonical adaptation protobuf")
    return obj

def _policy(w):
    return verify_policy(RoutingPolicy(
        w.policy_version,w.workspace_id,w.target,
        tuple(w.allowed_families),w.feature_count,
        tuple(tuple(a.values) for a in w.coefficients),
        tuple(w.intercepts),tuple(w.center),tuple(w.scale),
        w.training_digest,w.proposal_id,w.base_policy_digest,w.status,w.digest))

def _proposal(w):
    return AdaptationProposal(
        w.proposal_id,w.workspace_id,w.target,w.policy_version,w.source_digest,
        w.consent_receipt,w.privacy_class,tuple(w.allowed_families),
        w.retention_until_ms,w.train_before_ms,w.holdout_from_ms,
        w.base_policy_digest,w.maximum_training_rows,w.maximum_cpu_ms,
        w.rollback_policy_digest)

def _traces(messages):
    return tuple(Trace(
        v.event_id,v.occurred_ms,tuple(v.features),v.expected_route,
        v.source_digest,v.consent_receipt,v.retention_until_ms,
        v.privacy_class,v.task_family) for v in messages)

def _fill_eval(out,data):
    out.status=data.status;out.count=data.count;out.accuracy=data.accuracy
    out.log_loss=data.log_loss;out.worst_family_accuracy=data.worst_family_accuracy
    out.abstention_rate=data.abstention_rate;out.elapsed_ms=data.elapsed_ms

def execute_evaluation(request:bytes)->bytes:
    req=_read(request,pb.EvaluateRequest,MAX_INPUT)
    if (req.schema_version!=1 or not req.HasField("proposal")
            or not req.HasField("candidate") or not req.HasField("incumbent")):
        raise ValueError("missing typed comparison")
    p=_proposal(req.proposal)
    candidate=_policy(req.candidate)
    incumbent=_policy(req.incumbent)
    result=evaluate_promotion(p,candidate,incumbent,_traces(req.holdout))
    out=pb.EvaluateResult(
        schema_version=1,status=result.status,
        candidate_digest=result.candidate_digest,
        incumbent_digest=result.incumbent_digest,
        holdout_digest=result.holdout_digest,reasons=result.reasons,
        request_sha256=sha256(request).hexdigest(),limitations=result.limitations)
    _fill_eval(out.candidate_metrics,result.candidate)
    _fill_eval(out.incumbent_metrics,result.incumbent)
    frame=out.SerializeToString(deterministic=True)
    if len(frame)>MAX_RESULT:raise ValueError("oversized adaptation evaluation result")
    return frame

def verify_evaluation(request:bytes,response:bytes):
    actual=_read(response,pb.EvaluateResult,MAX_RESULT)
    expected=_read(execute_evaluation(request),pb.EvaluateResult,MAX_RESULT)
    if actual!=expected or actual.schema_version!=1:
        raise ValueError("adaptation evaluation fails independent replay")
    return actual
