"""G14 research-only composition of actual mature worker and G13 assurance evidence.

The two evidence sets describe INDEPENDENT fixtures and are NOT jointly
calibrated or bound to the same dataset. Worker numeric receipt validation is
shape/sanity verification, NOT authentication of the worker binary, library,
causal graph, synthetic ground truth, or Windows/Lu host identity.
"""
from __future__ import annotations
import hashlib
from cognitum import causal_integrated_assurance as g13
from cognitum import causal_mature_backend as mature
from cognitum.proto import causal_genuine_worker_assurance_pb2 as pb
from cognitum.proto import causal_mature_pb2 as m
from cognitum.proto import causal_integrated_assurance_pb2 as i

MAX_RESULT = 32768

def digest(value):
    return hashlib.sha256(value.SerializeToString(deterministic=True)).digest()


def _seal(req, decision):
    receipt=pb.WorkerAssuranceReceipt(
        request_sha256=digest(req),decision_sha256=digest(decision),
        mature_request_sha256=hashlib.sha256(req.mature_request_frame).digest(),
        mature_result_sha256=hashlib.sha256(req.mature_result_frame).digest(),
        integrated_receipt_sha256=digest(req.integrated_receipt),research_only=True)
    return decision,receipt


def calculate(req):
    if (not isinstance(req,pb.WorkerAssuranceRequest) or req.schema_version!=1
        or not all(g13._SCOPE.fullmatch(x) for x in
                   (req.trace_id,req.conversation_id,req.task_id))
        or not all(req.HasField(name) for name in
            ('integrated_request','integrated_decision','integrated_receipt'))
        or not 1<=len(req.mature_request_frame)<=mature.MAX_FRAME
        or not 1<=len(req.mature_result_frame)<=MAX_RESULT):
        raise ValueError('G14_INVALID_BOUNDED_REQUEST')
    out=pb.WorkerAssuranceDecision(
        schema_version=1,request_sha256=digest(req),research_only=True,
        disposition=pb.WORKER_ASSURANCE_REJECT_INVALID,
        safe_message='Evidence not verified. No causal conclusion or action is authorized.')
    # Critical: no model claims and no caller text are used as authorization.
    if (req.integrated_request.trace_id!=req.trace_id or
        req.integrated_request.conversation_id!=req.conversation_id or
        req.integrated_request.task_id!=req.task_id):
        out.reason_codes.append('G13_SCOPE_MISMATCH')
        return _seal(req,out)
    try:
        work_req, _ = mature._parse(req.mature_request_frame)
        work_result=mature._decode(req.mature_result_frame,m.MatureCausalResult)
    except (ValueError,TypeError,KeyError,IndexError):
        out.reason_codes.append('MATURE_WORKER_FRAME_NOT_VALID')
        return _seal(req,out)
    if work_req.trace_id != req.trace_id:
        out.reason_codes.append('WORKER_TRACE_SCOPE_MISMATCH')
        return _seal(req,out)
    verified=mature.verify_mature_receipt(req.mature_request_frame,req.mature_result_frame)
    if (not verified.request_bound_structure_checked or
        work_result.status != m.MATURE_RESULT_CANDIDATE):
        out.reason_codes.append('MATURE_RESULT_UNVERIFIED_OR_UNAVAILABLE')
        return _seal(req,out)
    out.genuine_worker_shape_verified=True
    out.runtime_backend_id=work_result.backend_id
    out.runtime_version=work_result.runtime_version
    # G13 includes replay of G10->G12, but is only synthetic-reference evidence.
    try:
        ok=g13.verify(req.integrated_request,req.integrated_decision,req.integrated_receipt)
    except (ValueError,TypeError,KeyError,IndexError,OSError):
        ok=False
    if not ok:
        out.reason_codes.append('G13_UPSTREAM_CHAIN_UNVERIFIED')
        return _seal(req,out)
    out.g13_chain_replayed=True
    out.reason_codes.extend(('NOT_AUTHENTICATED_RUNTIME_OR_LU_HOST',
        'WORKER_RESULT_NOT_CALIBRATED_BY_G9_G12_SYNTHETIC_STUDIES',
        'SCIENTIFIC_CANDIDATE_NOT_CAUSAL_IDENTIFICATION_PROOF'))
    if (req.caller_requests_real_world_action or
        req.caller_claims_worker_proves_causality or
        req.integrated_request.caller_intent in
          (i.CALLER_ASSERT_REAL_WORLD_CAUSAL_CLAIM,
           i.CALLER_RECOMMEND_INTERVENTION,i.CALLER_EXECUTE_EXTERNAL_ACTION)):
        out.disposition=pb.WORKER_ASSURANCE_ABSTAIN_CAUSAL_OR_ACTION
        out.reason_codes.append('UNAUTHORIZED_ESCALATION')
        out.safe_message='Abstain: scientific candidate results cannot grant causal certainty or action authority.'
    elif (req.integrated_decision.disposition !=
          i.INTEGRATION_DESCRIBE_SYNTHETIC_DIAGNOSTIC_ONLY):
        out.disposition=pb.WORKER_ASSURANCE_ABSTAIN_UPSTREAM
        out.reason_codes.append('UPSTREAM_G13_ABSTENTION_PRESERVED')
        out.safe_message='Abstain: upstream assurance did not approve a synthetic diagnostic.'
    else:
        out.disposition=pb.WORKER_ASSURANCE_RESEARCH_DIAGNOSTIC_ONLY
        out.reason_codes.append('INDEPENDENT_RESEARCH_OBSERVATIONS_ONLY')
        out.safe_message=(
           'A scientific worker returned a request-bound candidate result. '
           'Separate synthetic assurance evidence was replayed, but does not calibrate '
           'this worker result. Causal validity and host provenance are not established; '
           'no external action or real-world causal claim is authorized.')
    return _seal(req,out)


def verify(req,out,receipt):
    if not all((isinstance(req,pb.WorkerAssuranceRequest),
                isinstance(out,pb.WorkerAssuranceDecision),
                isinstance(receipt,pb.WorkerAssuranceReceipt))):
        return False
    if (not out.research_only or not receipt.research_only or
        out.worker_output_independently_authenticated or
        out.causal_identification_proven or out.calibrated_for_worker_dataset or
        out.authenticated_lu_host or out.may_trigger_external_action or
        out.may_issue_real_world_causal_claim or receipt.authenticated_lu_host):
        return False
    try:
        exp,rec=calculate(req)
        return (out.SerializeToString(deterministic=True)==exp.SerializeToString(deterministic=True)
                and receipt.SerializeToString(deterministic=True)==rec.SerializeToString(deterministic=True))
    except (ValueError,TypeError,OSError,KeyError,IndexError):
        return False
