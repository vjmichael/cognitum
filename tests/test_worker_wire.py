"""C02 strictly typed binary worker IPC; NO OS sandbox or process launcher."""
from dataclasses import replace
import unittest

try:
    from google.protobuf.message import DecodeError
except ModuleNotFoundError:
    raise unittest.SkipTest("optional Cognitum protobuf dependency unavailable")

from cognitum.capability_results import (
    CapabilityFailure, CapabilityResult, EvidenceRef, ExactRational,
)
from cognitum.protobuf_codec import (
    RATIONAL_REQUEST_TYPE, RATIONAL_RESULT_TYPE,
    encode_rational_request, NativeProtoOutput,
)
from cognitum.proto import worker_pb2 as pb
from cognitum.worker_wire import (
    MAX_WIRE_BYTES, WIRE_VERSION, OS_ISOLATION_ATTESTED,
    admission_status, start_isolated_worker,
    create_call, encode_call, decode_call, encode_reply, decode_reply,
)


def call():
    return create_call(call_id="req1", input_payload=encode_rational_request("1/3+1/6"))


def completed():
    return CapabilityResult(
        request_id="req1", correlation_id="session1", operation="calc.rational",
        operation_schema_version="1.0.0", status="completed",
        value=ExactRational("1/2"),
        evidence=(EvidenceRef("computation", "req1"),),
        limitations=("intent_not_verified",),
    )


def failed(code="permission_denied", status="denied", retryable=False):
    return CapabilityResult(
        request_id="req1", correlation_id="session1", operation="calc.rational",
        operation_schema_version="1.0.0", status=status,
        failure=CapabilityFailure(code, retryable),
        limitations=("no_computed_answer",),
    )


class SecureWorkerBoundaryTests(unittest.TestCase):
    def test_wire_schema_is_actual_protobuf_with_oneof(self):
        self.assertEqual(pb.DESCRIPTOR.package, "cognitum.worker.v1")
        self.assertEqual(pb.WorkerReply.DESCRIPTOR.oneofs_by_name["outcome"].name, "outcome")
        self.assertEqual([x.number for x in pb.WorkerCall.DESCRIPTOR.fields], list(range(1, 10)))
        self.assertEqual([x.number for x in pb.WorkerReply.DESCRIPTOR.fields], [1, 2, 3, 4])

    def test_call_roundtrip_and_strict_type_urls(self):
        obj = call()
        wire = encode_call(call_id="req1", input_payload=encode_rational_request("1/3+1/6"))
        self.assertEqual(decode_call(wire), obj)
        self.assertEqual(obj.input_type_url, RATIONAL_REQUEST_TYPE)
        self.assertEqual(obj.output_type_url, RATIONAL_RESULT_TYPE)
        self.assertNotEqual(wire[:1], b"{")
        self.assertLessEqual(len(wire), MAX_WIRE_BYTES)
        self.assertEqual(obj.timeout_ms, 2000)

    def test_timeout_and_ids_are_bounded_and_type_strict(self):
        for budget in (0, -1, 10001, True, 1.5, "2000"):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                create_call(call_id="req1", input_payload=encode_rational_request("1"),
                            timeout_ms=budget)
        for ident in ("", "req with spaces", "x" * 129, "é"):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                create_call(call_id=ident, input_payload=encode_rational_request("1"))

    def test_no_unreviewed_operation_or_tampered_domain_payload(self):
        message = call()
        for k, v in (
            ("native_tool_id", "lu.shell.exec"),
            ("operation", "hdc.retrieve"),
            ("operation_schema_version", "9.0.0"),
            ("input_type_url", "type.googleapis.com/lu.v1.ToolCall"),
            ("output_type_url", "type.googleapis.com/cognitum.v1.NumericalEstimateResult"),
            ("timeout_ms", 10001),
            ("protocol_version", 2),
            ("input", b"\x0a\xff"),
        ):
            with self.subTest(key=k):
                temp = pb.WorkerCall()
                temp.CopyFrom(message)
                setattr(temp, k, v)
                with self.assertRaises(ValueError):
                    decode_call(temp.SerializeToString(deterministic=True))

    def test_request_rejects_untrusted_input_types(self):
        with self.assertRaises(TypeError):
            create_call(call_id="req1", input_payload=b"fake")
        with self.assertRaises(ValueError):
            create_call(
                call_id="req1",
                input_payload=NativeProtoOutput(RATIONAL_RESULT_TYPE, b"\x0a\x011"),
            )
        with self.assertRaises(ValueError):
            create_call(
                call_id="req1",
                input_payload=NativeProtoOutput(RATIONAL_REQUEST_TYPE, b"\x00"),
            )

    def test_exact_success_reply_roundtrip_and_intent_limit(self):
        message = completed()
        wire = encode_reply(call(), message)
        parsed = pb.WorkerReply.FromString(wire)
        self.assertEqual(parsed.WhichOneof("outcome"), "success")
        self.assertEqual(parsed.success.output_type_url, RATIONAL_RESULT_TYPE)
        self.assertEqual(
            decode_reply(call(), wire, correlation_id="session1"), message,
        )

    def test_denial_timeout_and_error_have_no_computed_result(self):
        for code, status, retryable in (
            ("permission_denied", "denied", False),
            ("plugin_timed_out", "timed_out", True),
            ("invalid_plugin_response_or_worker_failure", "error", False),
        ):
            with self.subTest(status=status):
                result = failed(code, status, retryable)
                wire = encode_reply(call(), result)
                self.assertEqual(pb.WorkerReply.FromString(wire).WhichOneof("outcome"), "failure")
                decoded = decode_reply(call(), wire, correlation_id="session1")
                self.assertIsNone(decoded.value)
                self.assertEqual(decoded, result)

    def test_no_false_success_from_empty_or_wrong_protobuf(self):
        reply = pb.WorkerReply(protocol_version=WIRE_VERSION, call_id="req1")
        for variant in (reply,):
            with self.assertRaises(ValueError):
                decode_reply(call(), variant.SerializeToString(deterministic=True),
                             correlation_id="session1")
        reply.success.output_type_url = RATIONAL_RESULT_TYPE
        reply.success.output = b""
        with self.assertRaises(ValueError):
            decode_reply(call(), reply.SerializeToString(deterministic=True),
                         correlation_id="session1")

    def test_fail_closed_when_failure_code_unknown(self):
        reply = pb.WorkerReply(protocol_version=WIRE_VERSION, call_id="req1")
        reply.failure.code = "SECRET traceback from worker"
        with self.assertRaises(ValueError):
            decode_reply(call(), reply.SerializeToString(deterministic=True),
                         correlation_id="session1")
        reply.failure.code = "made_up"
        with self.assertRaises(ValueError):
            decode_reply(call(), reply.SerializeToString(deterministic=True),
                         correlation_id="session1")

    def test_denied_cannot_claim_retryable_true(self):
        reply = pb.WorkerReply(protocol_version=1, call_id="req1")
        reply.failure.code = "permission_denied"
        reply.failure.retryable = True
        with self.assertRaises(ValueError):
            decode_reply(call(), reply.SerializeToString(deterministic=True),
                         correlation_id="session1")

    def test_mismatched_call_id_and_operation_rejected(self):
        reply = pb.WorkerReply(protocol_version=1, call_id="other")
        reply.failure.code = "permission_denied"
        with self.assertRaises(ValueError):
            decode_reply(call(), reply.SerializeToString(deterministic=True),
                         correlation_id="session1")
        with self.assertRaises(ValueError):
            encode_reply(call(), replace(completed(), request_id="other"))
        with self.assertRaises(ValueError):
            encode_reply(call(), replace(completed(), operation="other"))

    def test_unknown_fields_and_noncanonical_encoding_rejected(self):
        wire = encode_call(call_id="req1", input_payload=encode_rational_request("1"))
        with self.assertRaises(ValueError):
            decode_call(wire + b"\x98\x06\x01")  # field 99 (unknown)
        with self.assertRaises(ValueError):
            decode_call(wire + b"\x08\x01")  # duplicate scalar protocol_version

    def test_reply_unknown_fields_or_two_oneof_arms_rejected(self):
        wire = encode_reply(call(), completed())
        with self.assertRaises(ValueError):
            decode_reply(call(), wire + b"\x98\x06\x01", correlation_id="session1")
        # protobuf last-one-wins would otherwise shadow a successful result.
        failure_field = b"\x22\x13\x0a\x11permission_denied"
        with self.assertRaises(ValueError):
            decode_reply(call(), wire + failure_field, correlation_id="session1")

    def test_invalid_frames_and_limits(self):
        for frame in (None, "not bytes", b"", b"\x00", b"\x0a\xff",
                      b"x" * (MAX_WIRE_BYTES + 1)):
            with self.subTest(frame=str(frame)[:20]), self.assertRaises(ValueError):
                decode_call(frame)
            with self.subTest(frame=str(frame)[:20]), self.assertRaises(ValueError):
                decode_reply(call(), frame, correlation_id="session1")

    def test_validated_only_not_reported_as_computation(self):
        result = CapabilityResult(
            request_id="req1", correlation_id="session1", operation="calc.rational",
            operation_schema_version="1.0.0", status="validated",
            limitations=("not_executed",),
        )
        with self.assertRaises(ValueError):
            encode_reply(call(), result)

    def test_lu_os_isolation_not_claimed_and_launch_always_denied(self):
        self.assertFalse(OS_ISOLATION_ATTESTED)
        state = admission_status()
        self.assertFalse(state.admitted)
        self.assertGreaterEqual(len(state.blockers), 5)
        with self.assertRaises(PermissionError):
            start_isolated_worker(authenticated=True, sandbox="appcontainer")
        with self.assertRaises(PermissionError):
            start_isolated_worker(object())

    def test_worker_protocol_contains_no_model_grant_or_sandbox_authority(self):
        field_names = {f.name for f in pb.WorkerCall.DESCRIPTOR.fields}
        for prohibited in ("grants", "subject_id", "user_id", "workspace_auth",
                           "sandboxed", "verified", "permission", "elevated",
                           "effect", "token", "credential"):
            self.assertNotIn(prohibited, field_names)


if __name__ == "__main__":
    unittest.main()
