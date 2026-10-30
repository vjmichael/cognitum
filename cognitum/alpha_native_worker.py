"""Fixed-function Cognitum process worker; no Lu authorization or OS sandbox."""
from __future__ import annotations
import struct
import sys
from .alpha_native import MAX_FRAME, MAX_REPLY, _parse
from .proto import alpha_native_pb2 as proto
from .protobuf_codec import decode_rational_request, encode_result, RATIONAL_REQUEST_TYPE
from .plugins.calculator import calculate
from .capability_results import CapabilityResult, EvidenceRef, ExactRational


def serve(input_stream, output_stream):
    header = input_stream.read(4)
    if len(header) != 4:
        return 2
    n = struct.unpack('>I', header)[0]
    if n <= 0 or n > MAX_FRAME:
        return 2
    raw = input_stream.read(n + 1)
    if len(raw) != n:
        return 2
    try:
        call = _parse(proto.Call, raw, MAX_FRAME)
        if call.version != 1 or call.operation != 'calc.rational' or call.request_type_url != RATIONAL_REQUEST_TYPE:
            return 2
        expression = decode_rational_request(call.request_type_url, call.request_payload)
        value = calculate(expression)
        answer = CapabilityResult(request_id=call.request_id, correlation_id=call.request_id,
                 operation='calc.rational', operation_schema_version='1.0.0',
                 status='completed', value=ExactRational(value),
                 evidence=(EvidenceRef('computation', call.request_id),),
                 limitations=('intent_not_verified',))
        encoded = encode_result(answer)
        reply = proto.Reply(version=1, request_id=call.request_id, status=proto.Reply.COMPLETED,
                            result_type_url=encoded.type_url, result_payload=encoded.payload)
        frame = reply.SerializeToString(deterministic=True)
        if len(frame) > MAX_REPLY:
            return 2
        output_stream.write(struct.pack('>I', len(frame)) + frame)
        output_stream.flush()
        return 0
    except (ValueError, TypeError, OverflowError):
        return 2

if __name__ == '__main__':
    sys.exit(serve(sys.stdin.buffer, sys.stdout.buffer))
