"""Protobuf domain-payload codec for Lu's native typed tool boundary.

Does NOT wrap, modify, or impersonate lu.v1.ToolCall/ToolReply. Lu's host
must provide the type URL, authorizer, selected model, and error/success arm.
Cognitum emits actual Protobuf bytes with exact type URLs and validates inputs
again after decoding. The resulting payloads are not a permission grant.
"""
from dataclasses import dataclass

try:
    from google.protobuf.message import DecodeError
    from .proto import capability_pb2 as pb
except ModuleNotFoundError as error:
    if error.name == "google" or error.name.startswith("google."):
        raise ImportError("Cognitum Protobuf requires pip install 'cognitum-core[proto]'") from error
    raise

from .capability_results import (
    CapabilityFailure, CapabilityResult, EvidenceRef, ExactRational,
    NumericalEstimate, RetrievedReferences,
)
from .contracts import Shape

TYPE_PREFIX = "type.googleapis.com/cognitum.v1."
RATIONAL_REQUEST_TYPE = TYPE_PREFIX + "CalculateRationalRequest"
RATIONAL_RESULT_TYPE = TYPE_PREFIX + "CalculateRationalResult"
NUMERICAL_RESULT_TYPE = TYPE_PREFIX + "NumericalEstimateResult"
RETRIEVAL_RESULT_TYPE = TYPE_PREFIX + "RetrievedReferencesResult"
MAX_PROTO_BYTES = 16 * 1024
# These mappings belong to Cognitum's proposed operations, NOT Lu's registry.
_RESULTS = {
    "calc.rational": (ExactRational, pb.CalculateRationalResult, RATIONAL_RESULT_TYPE),
    "kan.predict": (NumericalEstimate, pb.NumericalEstimateResult, NUMERICAL_RESULT_TYPE),
    "hdc.retrieve": (RetrievedReferences, pb.RetrievedReferencesResult, RETRIEVAL_RESULT_TYPE),
}


@dataclass(frozen=True)
class NativeProtoOutput:
    """Result payload proposed for Lu's ToolOutput::ProtoPayload success arm."""
    type_url: str
    payload: bytes


@dataclass(frozen=True)
class NativeFailureProposal:
    """Proposed Lu ToolFailure fields. Never masquerades as ToolOutput success."""
    code: str
    retryable: bool

    def as_protobuf(self):
        return pb.CapabilityFailure(code=self.code, retryable=self.retryable)


def _parse(message_type, payload):
    if type(payload) is not bytes or len(payload) > MAX_PROTO_BYTES:
        raise ValueError("invalid or oversized Protobuf payload")
    message = message_type()
    try:
        message.ParseFromString(payload)
    except DecodeError as error:
        raise ValueError("malformed Protobuf bytes") from error
    # Standard protobuf readers preserve unknown fields. Until schema migration
    # is explicitly reviewed, reject them rather than silently discard.
    without_unknowns = message_type()
    without_unknowns.CopyFrom(message)
    without_unknowns.DiscardUnknownFields()
    if message != without_unknowns:
        raise ValueError("unknown Protobuf fields are not accepted")
    return message


def _wire_bytes(message):
    payload = message.SerializeToString(deterministic=True)
    if len(payload) > MAX_PROTO_BYTES:
        raise ValueError("oversized Protobuf output")
    return payload


def encode_rational_request(expression):
    """Typed inert request only; not authorization, tool selection or execution."""
    Shape((("expression", 256),)).validate({"expression": expression})
    return NativeProtoOutput(
        RATIONAL_REQUEST_TYPE,
        _wire_bytes(pb.CalculateRationalRequest(expression=expression)),
    )


def decode_rational_request(type_url, payload):
    if type_url != RATIONAL_REQUEST_TYPE:
        raise ValueError("unexpected request type URL")
    message = _parse(pb.CalculateRationalRequest, payload)
    Shape((("expression", 256),)).validate({"expression": message.expression})
    return message.expression


def encode_result(result):
    """Success maps to type-URL+Protobuf bytes; all other states map to failure.

    Lu is responsible for translating NativeFailureProposal into its own
    ToolFailure/ToolReply.failure. Dry-run validation is not a computed value.
    """
    if not isinstance(result, CapabilityResult):
        raise TypeError("validated CapabilityResult required")
    result.to_dict()  # validates bounded public shape
    if result.status != "completed":
        if result.status == "validated":
            return NativeFailureProposal("not_executed", False)
        if not isinstance(result.failure, CapabilityFailure):
            raise ValueError("non-completed result requires a sanitized typed failure")
        return NativeFailureProposal(result.failure.code, result.failure.retryable)
    entry = _RESULTS.get(result.operation)
    if entry is None or type(result.value) is not entry[0]:
        raise ValueError("domain value does not match the declared operation")
    _, message_type, type_url = entry
    value = result.value
    message = message_type()
    if isinstance(value, ExactRational):
        if not any(e.kind == "computation" for e in result.evidence):
            raise ValueError("exact arithmetic requires computation provenance")
        message.value = value.value
    elif isinstance(value, NumericalEstimate):
        message.value = value.value
        message.method = value.method
        if value.lower is not None:
            message.lower = value.lower
            message.upper = value.upper
    else:
        if not any(e.kind == "source_snapshot" and e.ref == value.source_snapshot_id
                   for e in result.evidence):
            raise ValueError("retrieval requires its matching source snapshot evidence")
        message.candidates.extend(value.candidates)
        message.source_snapshot_id = value.source_snapshot_id
        message.index_source_snapshot_id = value.index_source_snapshot_id
    for ref in result.evidence:
        message.evidence.add(kind=ref.kind, ref=ref.ref)
    message.limitations.extend(result.limitations)
    return NativeProtoOutput(type_url, _wire_bytes(message))


def decode_success(operation, type_url, payload, *, request_id, correlation_id,
                   operation_schema_version="1.0.0"):
    """Decode a Lu-authorized success body; preserve required epistemic limits."""
    entry = _RESULTS.get(operation)
    if entry is None or type_url != entry[2]:
        raise ValueError("unknown or mismatched native output type URL")
    value_class, message_type, _ = entry
    message = _parse(message_type, payload)
    if value_class is ExactRational:
        value = ExactRational(message.value)
    elif value_class is NumericalEstimate:
        lower = message.lower if message.HasField("lower") else None
        upper = message.upper if message.HasField("upper") else None
        value = NumericalEstimate(message.value, message.method, lower, upper)
    else:
        value = RetrievedReferences(
            tuple(message.candidates), message.source_snapshot_id,
            message.index_source_snapshot_id,
        )
    evidence = tuple(EvidenceRef(x.kind, x.ref) for x in message.evidence)
    limitations = tuple(message.limitations)
    verified = CapabilityResult(
        request_id=request_id, correlation_id=correlation_id,
        operation=operation, operation_schema_version=operation_schema_version,
        status="completed", value=value, evidence=evidence,
        limitations=limitations,
    )
    # Enforce domain-specific provenance as well as capability contract checks.
    candidate = encode_result(verified)
    if candidate.type_url != type_url:
        raise ValueError("invalid domain mapping")
    return verified


def decode_failure_from_worker(payload, *, status, request_id,
                               correlation_id, operation,
                               operation_schema_version="1.0.0"):
    """For internal worker-produced cognitum.v1.CapabilityFailure bytes only.

    Lu-native ToolReply.failure uses lu.v1.ToolError, NOT this message.
    Host identity/status must come from a trusted source, never this payload.
    """
    message = _parse(pb.CapabilityFailure, payload)
    return CapabilityResult(
        request_id=request_id, correlation_id=correlation_id,
        operation=operation, operation_schema_version=operation_schema_version,
        status=status,
        failure=CapabilityFailure(message.code, message.retryable),
        limitations=("no_computed_answer",),
    )
