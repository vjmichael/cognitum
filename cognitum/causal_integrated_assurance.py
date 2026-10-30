"""G13 end-to-end, strictly non-authorizing research-only assurance adapter.

Model-supplied text is never parsed as authority, executed, or echoed. This
adapter checks actual G10/G11/G12 Protobuf request/decision/receipt chains and
returns a new request-bound research receipt. Every receipt is a deterministic
replay checksum, NOT a signature, authenticated host admission, or action grant.
"""
import hashlib
import re
from pathlib import Path
from cognitum import causal_adversarial_assurance as g12
from cognitum.proto import causal_integrated_assurance_pb2 as pb
from cognitum.proto import causal_assurance_policy_pb2 as g10_pb

PINNED_G12_SOURCE_SHA256 = '7fc1223c04d52d076680cc00152a7e1590d539b44dbc2ea2b7ed06e534def703'
_SCOPE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z', re.ASCII)


def digest(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).digest()


def validate_request(req):
    if (not isinstance(req, pb.IntegratedAssuranceRequest)
        or req.schema_version != 1
        or not all(_SCOPE.fullmatch(s) for s in (req.trace_id, req.conversation_id, req.task_id))
        or not all(req.HasField(k) for k in ('upstream_request', 'upstream_decision', 'upstream_receipt'))
        or len(req.untrusted_caller_narrative.encode('utf-8')) > 4096):
        raise ValueError('G13_INVALID_TYPED_SCOPED_REQUEST')


def _seal(req, decision):
    return decision, pb.IntegratedAssuranceReceipt(
        request_sha256=digest(req), decision_sha256=digest(decision),
        upstream_receipt_sha256=digest(req.upstream_receipt),
        pinned_g12_source_sha256=decision.pinned_g12_source_sha256,
        research_only=True, authenticated_lu_host=False,
    )


def calculate(req):
    """Offline research advisory; cannot authorize an intervention or tool.

    The G12 request contains an actual G11 request and G10 calculation evidence.
    Successful verification permits, at most, an explicit synthetic stress
    diagnostic, never a point-causal conclusion or real-world action.
    """
    validate_request(req)
    out = pb.IntegratedAssuranceDecision(
        schema_version=1, trace_id=req.trace_id, conversation_id=req.conversation_id,
        task_id=req.task_id, request_sha256=digest(req), research_only=True,
        disposition=pb.INTEGRATION_REJECT_UNVERIFIED,
        safe_message='Evidence verification failed. No causal claim or action is authorized.',
    )
    path = Path(g12.__file__)
    try:
        approved_g12 = hashlib.sha256(path.read_bytes()).hexdigest() == PINNED_G12_SOURCE_SHA256
    except OSError:
        approved_g12 = False
    if not approved_g12:
        out.reason_codes.append('UNAPPROVED_G12_SOURCE')
        return _seal(req, out)
    out.pinned_g12_source_sha256 = bytes.fromhex(PINNED_G12_SOURCE_SHA256)

    # Protobuf receipt replay is not publisher authentication or a Lu host grant.
    try:
        replay_ok = g12.verify(req.upstream_request, req.upstream_decision, req.upstream_receipt)
    except (ValueError, TypeError, OSError, KeyError, IndexError, RuntimeError):
        replay_ok = False
    if not replay_ok:
        out.reason_codes.append('G12_REQUEST_DECISION_RECEIPT_REPLAY_FAILED')
        return _seal(req, out)
    d12 = req.upstream_decision
    d11 = req.upstream_request.upstream_decision
    d10 = req.upstream_request.upstream_request.upstream_decision
    out.g10_replay_checked = True
    out.g11_replay_checked = True
    out.g12_replay_checked = True
    out.g10_disposition = g10_pb.CausalAssuranceDisposition.Name(d10.disposition)
    out.g11_disposition = d11.disposition
    out.g12_disposition = d12.disposition
    out.independent_synthetic_arithmetic_replayed = bool(
        d12.independent_evidence_math_verified and
        req.upstream_receipt.independent_arithmetic_replayed)

    if (d12.disposition == 'REJECT_UNVERIFIED' or not out.independent_synthetic_arithmetic_replayed):
        out.reason_codes.append('G12_EVIDENCE_NOT_ADMITTED')
        return _seal(req, out)
    out.reason_codes.extend((
        'RESEARCH_ONLY_NOT_HOST_AUTHORIZATION',
        'CALCULATION_REPLAY_NOT_IDENTIFICATION_PROOF',
        'UNKNOWN_REAL_WORLD_GENERALIZATION',
    ))
    # Reject asserted privileges regardless of the caller's natural-language story.
    if req.caller_claims_causal_proof or req.caller_claims_lu_authorization:
        out.disposition = pb.INTEGRATION_ABSTAIN_UNTRUSTED_ASSERTION
        out.reason_codes.append('MODEL_CANNOT_ATTEST_CAUSAL_TRUTH_OR_HOST_AUTHORITY')
        out.safe_message = 'Abstain: caller asserted unverified causal proof or Lu authority.'
    elif (req.caller_intent in (pb.CALLER_ASSERT_REAL_WORLD_CAUSAL_CLAIM,
                                pb.CALLER_RECOMMEND_INTERVENTION,
                                pb.CALLER_EXECUTE_EXTERNAL_ACTION)
          or req.upstream_request.requests_intervention_recommendation
          or req.upstream_request.upstream_request.upstream_request.requests_intervention_recommendation):
        out.disposition = pb.INTEGRATION_ABSTAIN_CAUSAL_OVERREACH
        out.reason_codes.append('MODEL_REQUESTED_UNSUPPORTED_CAUSAL_CLAIM_OR_ACTION')
        out.safe_message = 'Abstain: research evidence cannot justify this causal claim or intervention.'
    elif req.caller_intent != pb.CALLER_DESCRIBE_SYNTHETIC_STRESS_TEST:
        out.disposition = pb.INTEGRATION_ABSTAIN_UNSUPPORTED_INTENT
        out.reason_codes.append('UNRECOGNIZED_OR_UNSPECIFIED_INTENT')
        out.safe_message = 'Abstain: only a qualified synthetic stress-test description is supported.'
    elif not d12.may_describe_synthetic_stress_diagnostic:
        out.disposition = pb.INTEGRATION_ABSTAIN_UPSTREAM
        out.reason_codes.append('UPSTREAM_ABSTENTION_BLOCKS_SYNTHETIC_DIAGNOSTIC')
        out.safe_message = 'Abstain: upstream review does not permit even this synthetic description.'
    else:
        out.disposition = pb.INTEGRATION_DESCRIBE_SYNTHETIC_DIAGNOSTIC_ONLY
        out.may_describe_synthetic_stress_diagnostic = True
        out.reason_codes.extend((
            'SYNTHETIC_STRESS_DIAGNOSTIC_ONLY',
            'G12_POINT_CAUSAL_GENERALIZATION_STILL_ABSTAINED',
        ))
        out.safe_message = (
            'Synthetic stress-test arithmetic was independently replayed. '
            'The causal graph, transportability, and real-world effect are not verified. '
            'No causal conclusion, recommendation, or external action is authorized.'
        )
    # Caller narrative is intentionally never inspected or reflected in the output.
    # All authority and identification flags remain their false proto3 defaults.
    return _seal(req, out)


def verify(req, out, receipt):
    if not (isinstance(req, pb.IntegratedAssuranceRequest)
            and isinstance(out, pb.IntegratedAssuranceDecision)
            and isinstance(receipt, pb.IntegratedAssuranceReceipt)):
        return False
    if (not out.research_only or not receipt.research_only
        or out.synthetic_generator_authenticity_verified or out.causal_identification_proven
        or out.may_issue_real_world_causal_claim or out.may_recommend_intervention
        or out.may_trigger_external_action or out.authenticated_lu_host
        or receipt.authenticated_lu_host):
        return False
    try:
        expected, expected_receipt = calculate(req)
        return (out.SerializeToString(deterministic=True) == expected.SerializeToString(deterministic=True)
            and receipt.SerializeToString(deterministic=True) == expected_receipt.SerializeToString(deterministic=True))
    except (ValueError, TypeError, OSError, KeyError, IndexError):
        return False
