"""Real binary Protobuf codec tests for optional Cognitum Lu-native domain data."""
import unittest

from cognitum.capability_results import (
    CapabilityFailure, CapabilityResult, EvidenceRef, ExactRational,
    NumericalEstimate, RetrievedReferences, from_runtime_response,
)
from cognitum.contracts import HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.proto import capability_pb2 as pb
from cognitum.protobuf_codec import (
    RATIONAL_REQUEST_TYPE, RATIONAL_RESULT_TYPE,
    NUMERICAL_RESULT_TYPE, RETRIEVAL_RESULT_TYPE,
    NativeFailureProposal, NativeProtoOutput,
    decode_failure_from_worker, decode_rational_request, decode_success,
    encode_rational_request, encode_result,
)


def make(value=None, *, operation="calc.rational", status="completed",
         failure=None, limitations=None, evidence=None):
    if limitations is None:
        if isinstance(value, ExactRational):
            limitations = ("intent_not_verified",)
        elif isinstance(value, NumericalEstimate):
            limitations = ("intent_not_verified", "bounds_not_probabilistic" if
                           value.lower is not None else "uncertainty_unquantified")
        elif isinstance(value, RetrievedReferences):
            limitations = ("retrieval_not_truth", "no_permission_conferred")
        else:
            limitations = ("no_computed_answer",)
    if evidence is None:
        if isinstance(value, RetrievedReferences):
            evidence = (EvidenceRef("source_snapshot", value.source_snapshot_id),)
        elif value is not None:
            evidence = (EvidenceRef("computation", "req1"),)
        else:
            evidence = ()
    return CapabilityResult(
        request_id="req1", correlation_id="turn1", operation=operation,
        operation_schema_version="1.0.0", status=status, value=value,
        evidence=evidence, limitations=limitations, failure=failure,
    )


def roundtrip(typed):
    encoded = encode_result(typed)
    assert isinstance(encoded, NativeProtoOutput)
    return decode_success(typed.operation, encoded.type_url, encoded.payload,
                          request_id=typed.request_id, correlation_id=typed.correlation_id)


class NativeProtoCodecTests(unittest.TestCase):
    def test_exact_request_is_real_protobuf_binary(self):
        encoded = encode_rational_request("1/3 + 1/6")
        self.assertEqual(encoded.type_url, RATIONAL_REQUEST_TYPE)
        self.assertEqual(pb.CalculateRationalRequest.FromString(encoded.payload).expression,
                         "1/3 + 1/6")
        self.assertEqual(decode_rational_request(encoded.type_url, encoded.payload),
                         "1/3 + 1/6")
        self.assertNotEqual(encoded.payload, b'{"expression":"1/3 + 1/6"}')

    def test_request_bounded_and_strict(self):
        for expression in (None, 1, True, "", "1"*257):
            with self.subTest(v=str(expression)[:8]), self.assertRaises(ValueError):
                encode_rational_request(expression)
        with self.assertRaises(ValueError):
            decode_rational_request("type.googleapis.com/lu.v1.LegacyJsonArguments",
                                    encode_rational_request("1").payload)

    def test_exact_result_uses_declared_type_url_and_roundtrips(self):
        original = make(ExactRational("1/2"))
        encoded = encode_result(original)
        self.assertEqual(encoded.type_url, RATIONAL_RESULT_TYPE)
        wire = pb.CalculateRationalResult.FromString(encoded.payload)
        self.assertEqual(wire.value, "1/2")
        self.assertEqual(list(wire.limitations), ["intent_not_verified"])
        self.assertEqual(roundtrip(original), original)

    def test_live_standalone_calculator_to_protobuf_without_lu(self):
        registry = Registry()
        registry.install(Calculator, enabled=True)
        registry.nominate("calc", "reference_calc")
        legacy = Runtime(registry).call(
            Request("req1", "turn1", "calc.rational", {"expression": "1/3+1/6"}),
            HostContext("local", "local-user"))
        original = legacy.to_dict()
        typed = from_runtime_response(legacy)
        payload = encode_result(typed)
        self.assertEqual(payload.type_url, RATIONAL_RESULT_TYPE)
        self.assertEqual(pb.CalculateRationalResult.FromString(payload.payload).value, "1/2")
        self.assertEqual(roundtrip(typed), typed)
        self.assertEqual(legacy.to_dict(), original)

    def test_numerical_optional_absent_and_present_zero(self):
        empty_bounds = make(NumericalEstimate("0", "kan.v1"), operation="kan.predict")
        encoded = encode_result(empty_bounds)
        self.assertEqual(encoded.type_url, NUMERICAL_RESULT_TYPE)
        parsed = pb.NumericalEstimateResult.FromString(encoded.payload)
        self.assertFalse(parsed.HasField("lower"))
        self.assertFalse(parsed.HasField("upper"))
        self.assertEqual(roundtrip(empty_bounds), empty_bounds)

        bounds = make(NumericalEstimate("0", "kan.v1", "0", "0"),
                      operation="kan.predict")
        parsed = pb.NumericalEstimateResult.FromString(encode_result(bounds).payload)
        self.assertTrue(parsed.HasField("lower"))
        self.assertTrue(parsed.HasField("upper"))
        self.assertEqual(parsed.lower, "0")
        self.assertEqual(roundtrip(bounds), bounds)

    def test_retrieval_snapshot_evidence_not_authority(self):
        original = make(RetrievedReferences(("item1", "item2"), "v7", "v7"),
                        operation="hdc.retrieve")
        encoded = encode_result(original)
        self.assertEqual(encoded.type_url, RETRIEVAL_RESULT_TYPE)
        self.assertEqual(tuple(pb.RetrievedReferencesResult.FromString(
            encoded.payload).candidates), ("item1", "item2"))
        self.assertEqual(roundtrip(original), original)

    def test_retrieval_requires_real_snapshot_ref(self):
        data = make(RetrievedReferences(("item1",), "rev1", "rev1"),
                    operation="hdc.retrieve",
                    evidence=(EvidenceRef("computation", "req1"),))
        with self.assertRaises(ValueError):
            encode_result(data)
        invalid = pb.RetrievedReferencesResult(
            candidates=["a"], source_snapshot_id="rev1",
            index_source_snapshot_id="rev2",
        )
        invalid.evidence.add(kind="source_snapshot", ref="rev1")
        invalid.limitations.extend(("retrieval_not_truth", "no_permission_conferred"))
        with self.assertRaises(ValueError):
            decode_success("hdc.retrieve", RETRIEVAL_RESULT_TYPE,
                           invalid.SerializeToString(), request_id="req1",
                           correlation_id="turn1")

    def test_no_success_for_failure_or_validation_only(self):
        denied = make(status="denied", failure=CapabilityFailure("permission_denied"))
        mapped = encode_result(denied)
        self.assertIsInstance(mapped, NativeFailureProposal)
        self.assertEqual(mapped.code, "permission_denied")
        self.assertFalse(mapped.retryable)
        self.assertEqual(pb.CapabilityFailure.FromString(
            mapped.as_protobuf().SerializeToString()).code, "permission_denied")

        dry = make(status="validated", limitations=("not_executed",))
        result = encode_result(dry)
        self.assertIsInstance(result, NativeFailureProposal)
        self.assertEqual(result.code, "not_executed")

    def test_failure_worker_protobuf_never_claims_success(self):
        wire = pb.CapabilityFailure(code="plugin_timed_out", retryable=True)
        typed = decode_failure_from_worker(
            wire.SerializeToString(), status="timed_out", request_id="req1",
            correlation_id="turn1", operation="calc.rational")
        self.assertIsNone(typed.value)
        self.assertEqual(typed.failure.code, "plugin_timed_out")
        self.assertIsInstance(encode_result(typed), NativeFailureProposal)
        with self.assertRaises(ValueError):
            decode_failure_from_worker(
                wire.SerializeToString(), status="completed",
                request_id="req1", correlation_id="turn1", operation="calc.rational")

    def test_wrong_type_urls_and_operation_mismatch_are_rejected(self):
        encoded = encode_result(make(ExactRational("2")))
        for type_url in (RATIONAL_REQUEST_TYPE, NUMERICAL_RESULT_TYPE,
                         "type.googleapis.com/lu.v1.ToolReply"):
            with self.subTest(type_url=type_url), self.assertRaises(ValueError):
                decode_success("calc.rational", type_url, encoded.payload,
                               request_id="req1", correlation_id="turn1")
        with self.assertRaises(ValueError):
            encode_result(make(ExactRational("2"), operation="kan.predict"))

    def test_malformed_oversize_and_missing_data_fail(self):
        for payload in (b"\x0a\xff", b"\x00", b"x"*(16384+1), "str", None, b""):
            with self.subTest(payload=str(payload)[:30]), self.assertRaises(ValueError):
                decode_success("calc.rational", RATIONAL_RESULT_TYPE, payload,
                               request_id="req1", correlation_id="turn1")

    def test_unknown_fields_cannot_be_silently_ignored(self):
        known = encode_result(make(ExactRational("2")))
        # field 99 varint 1 is unknown to the v1 schema
        with self.assertRaises(ValueError):
            decode_success("calc.rational", RATIONAL_RESULT_TYPE,
                           known.payload + b"\x98\x06\x01", request_id="req1",
                           correlation_id="turn1")
        with self.assertRaises(ValueError):
            decode_rational_request(
                RATIONAL_REQUEST_TYPE,
                encode_rational_request("1").payload + b"\x98\x06\x01")

    def test_reject_missing_limitations_and_evidence(self):
        msg = pb.CalculateRationalResult(value="2")
        msg.evidence.add(kind="computation", ref="req1")
        with self.assertRaises(ValueError):
            decode_success("calc.rational", RATIONAL_RESULT_TYPE,
                           msg.SerializeToString(), request_id="req1",
                           correlation_id="turn1")
        msg.ClearField("evidence")
        msg.limitations.append("intent_not_verified")
        with self.assertRaises(ValueError):
            decode_success("calc.rational", RATIONAL_RESULT_TYPE,
                           msg.SerializeToString(), request_id="req1",
                           correlation_id="turn1")

    def test_invalid_explicit_empty_numerical_bound_rejected(self):
        msg = pb.NumericalEstimateResult(value="0", method="kan.v1")
        msg.lower = ""
        msg.upper = "1"
        msg.evidence.add(kind="computation", ref="req1")
        msg.limitations.extend(("intent_not_verified", "bounds_not_probabilistic"))
        self.assertTrue(msg.HasField("lower"))
        with self.assertRaises(ValueError):
            decode_success("kan.predict", NUMERICAL_RESULT_TYPE,
                           msg.SerializeToString(), request_id="req1",
                           correlation_id="turn1")

    def test_proto_has_expected_package_and_field_numbers(self):
        self.assertEqual(pb.DESCRIPTOR.package, "cognitum.v1")
        fields = pb.NumericalEstimateResult.DESCRIPTOR.fields_by_name
        self.assertEqual([fields[n].number for n in
                          ("value", "method", "lower", "upper", "evidence", "limitations")],
                         [1, 2, 3, 4, 5, 6])
        self.assertTrue(fields["lower"].has_presence)
        self.assertTrue(fields["upper"].has_presence)


if __name__ == "__main__":
    unittest.main()
