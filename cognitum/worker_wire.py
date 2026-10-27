"""C02 Protobuf-only, host-gated worker IPC. NO sandbox or launcher here.

The legacy multiprocessing worker is trusted-code smoke infrastructure and
still uses Python pickle for process arguments/replies. Do not connect it to
this IPC and do not run untrusted extensions through it. This new protocol
accepts only the *reviewed inert* calc.rational domain and provides typed
bounded requests/replies for a FUTURE Lu OS-confined native worker supervisor.

All identity/permission/OS-isolation decisions belong to Lu's trusted host,
not to these bytes. A model cannot confer authority by constructing a frame.
"""
from dataclasses import dataclass
import re

from google.protobuf.message import DecodeError

from .capability_results import CapabilityFailure, CapabilityResult
from .protobuf_codec import (
    NativeFailureProposal, NativeProtoOutput, RATIONAL_REQUEST_TYPE,
    RATIONAL_RESULT_TYPE, decode_rational_request, decode_success,
    encode_result,
)
from .proto import worker_pb2 as pb

WIRE_VERSION = 1
MAX_WIRE_BYTES = 16 * 1024
TOOL_ID = "cognitum.calc.rational"
OPERATION = "calc.rational"
OPERATION_SCHEMA_VERSION = "1.0.0"
_CALL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_ERRORS = {
    "invalid_request": "invalid_input",
    "invalid_operation_input": "invalid_input",
    "plugin_invalid_input": "invalid_input",
    "capability_unavailable": "unavailable",
    "identity_scope_mismatch": "denied",
    "permission_denied": "denied",
    "effectful_execution_not_implemented": "denied",
    "replay_requires_inert_deterministic_operation": "denied",
    "plugin_timed_out": "timed_out",
    "plugin_error": "error",
    "invalid_plugin_response_or_worker_failure": "error",
}
# Never enable untrusted/effectful workers on a Python-only boundary.
OS_ISOLATION_ATTESTED = False
_MISSING_OS_CONTROLS = (
    "no_lu_host_bound_subject_or_grant",
    "no_verified_os_process_token_and_filesystem_confinement",
    "no_verified_network_and_handle_denial",
    "no_process_tree_quotas_cancel_and_reap",
    "no_authenticated_supervisor_channel",
)


@dataclass(frozen=True)
class WorkerLaunchGate:
    """Diagnostic, immutable admission status; NEVER a permission token."""
    admitted: bool = False
    blockers: tuple[str, ...] = _MISSING_OS_CONTROLS


def admission_status():
    """C02 does not provide a public path to successful worker admission."""
    return WorkerLaunchGate()


def start_isolated_worker(*_args, **_kwargs):
    """Fail closed even if caller supplies a fake 'authorized' object."""
    raise PermissionError("lu_verified_worker_isolation_and_authority_unavailable")


def _valid_call_id(call_id):
    if type(call_id) is not str or not _CALL_ID.fullmatch(call_id):
        raise ValueError("invalid worker call id")


def _parse(message_cls, data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_WIRE_BYTES:
        raise ValueError("invalid or oversized worker wire frame")
    message = message_cls()
    try:
        message.ParseFromString(data)
    except DecodeError as error:
        raise ValueError("malformed worker protobuf frame") from error
    without_unknown = message_cls()
    without_unknown.CopyFrom(message)
    without_unknown.DiscardUnknownFields()
    if without_unknown != message:
        raise ValueError("unknown worker protobuf fields")
    # Deny duplicate scalar tags, shadowed oneof values, and ambiguous bytes.
    # A future external Lu host must use deterministic serialization too.
    if message.SerializeToString(deterministic=True) != data:
        raise ValueError("noncanonical worker protobuf frame")
    return message


def _serialized(message):
    frame = message.SerializeToString(deterministic=True)
    if not 0 < len(frame) <= MAX_WIRE_BYTES:
        raise ValueError("worker protobuf frame too large")
    return frame


def create_call(*, call_id, input_payload: NativeProtoOutput, timeout_ms=2000):
    """Inert host-side framing only; never spawns or authorizes a worker."""
    _valid_call_id(call_id)
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 10000:
        raise ValueError("invalid worker timeout")
    if not isinstance(input_payload, NativeProtoOutput):
        raise TypeError("trusted typed request bytes required")
    if input_payload.type_url != RATIONAL_REQUEST_TYPE:
        raise ValueError("unapproved input protobuf message type")
    # Parse the actual domain payload (not just the declared type URL).
    decode_rational_request(input_payload.type_url, input_payload.payload)
    message = pb.WorkerCall(
        protocol_version=WIRE_VERSION,
        call_id=call_id,
        native_tool_id=TOOL_ID,
        operation=OPERATION,
        operation_schema_version=OPERATION_SCHEMA_VERSION,
        input_type_url=RATIONAL_REQUEST_TYPE,
        input=input_payload.payload,
        output_type_url=RATIONAL_RESULT_TYPE,
        timeout_ms=timeout_ms,
    )
    _serialized(message)
    return message


def decode_call(frame):
    call = _parse(pb.WorkerCall, frame)
    _valid_call_id(call.call_id)
    if (call.protocol_version != WIRE_VERSION
            or call.native_tool_id != TOOL_ID
            or call.operation != OPERATION
            or call.operation_schema_version != OPERATION_SCHEMA_VERSION
            or call.input_type_url != RATIONAL_REQUEST_TYPE
            or call.output_type_url != RATIONAL_RESULT_TYPE
            or not 1 <= call.timeout_ms <= 10000):
        raise ValueError("unapproved native worker operation or protocol")
    decode_rational_request(call.input_type_url, call.input)
    return call


def encode_call(*, call_id, input_payload, timeout_ms=2000):
    return _serialized(create_call(
        call_id=call_id, input_payload=input_payload, timeout_ms=timeout_ms,
    ))


def encode_reply(call: pb.WorkerCall, result: CapabilityResult):
    """Return typed success or sanitized failure; never free-text error."""
    if not isinstance(call, pb.WorkerCall):
        raise TypeError("verified worker call expected")
    decode_call(_serialized(call))
    if not isinstance(result, CapabilityResult):
        raise TypeError("typed result required")
    if (result.request_id != call.call_id
            or result.operation != call.operation
            or result.operation_schema_version != call.operation_schema_version):
        raise ValueError("worker result correlation/operation mismatch")
    if result.status == "validated":
        raise ValueError("dry-run cannot be sent as a worker execution reply")
    result_bytes = encode_result(result)
    reply = pb.WorkerReply(protocol_version=WIRE_VERSION, call_id=call.call_id)
    if isinstance(result_bytes, NativeProtoOutput):
        if result_bytes.type_url != call.output_type_url:
            raise ValueError("worker result has unexpected type URL")
        reply.success.output_type_url = result_bytes.type_url
        reply.success.output = result_bytes.payload
    elif isinstance(result_bytes, NativeFailureProposal):
        if result_bytes.code not in _ERRORS:
            raise ValueError("worker emitted unknown failure category")
        reply.failure.code = result_bytes.code
        reply.failure.retryable = result_bytes.retryable
    else:
        raise TypeError("unknown worker result type")
    return _serialized(reply)


def decode_reply(call: pb.WorkerCall, frame: bytes, *, correlation_id: str):
    """Decode an untrusted reply, insisting that only Lu's call ID can match.

    NOTE: correlation_id is for response metadata, NOT a user credential.
    Actual authenticated subject/session binding is Lu's separate task.
    """
    if not isinstance(call, pb.WorkerCall):
        raise TypeError("verified worker call expected")
    decode_call(_serialized(call))
    reply = _parse(pb.WorkerReply, frame)
    if (reply.protocol_version != WIRE_VERSION
            or reply.call_id != call.call_id):
        raise ValueError("worker response correlation/version mismatch")
    outcome = reply.WhichOneof("outcome")
    if outcome == "success":
        if reply.success.output_type_url != call.output_type_url:
            raise ValueError("worker response has unexpected output type URL")
        return decode_success(
            call.operation, reply.success.output_type_url, reply.success.output,
            request_id=call.call_id, correlation_id=correlation_id,
            operation_schema_version=call.operation_schema_version,
        )
    if outcome == "failure":
        code = reply.failure.code
        status = _ERRORS.get(code)
        if status is None:
            raise ValueError("worker returned unknown failure category")
        return CapabilityResult(
            request_id=call.call_id,
            correlation_id=correlation_id,
            operation=call.operation,
            operation_schema_version=call.operation_schema_version,
            status=status,
            failure=CapabilityFailure(code, reply.failure.retryable),
            limitations=("no_computed_answer",),
        )
    raise ValueError("worker has neither a success nor a failure outcome")
