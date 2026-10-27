"""C05 differential and adversarial exact arithmetic tests (NO Lu model)."""
from decimal import Decimal
from fractions import Fraction
import random
import unittest

from cognitum.exact_reference import reference_calculate
from cognitum.plugins.calculator import Calculator, calculate


class C05ArithmeticVerification(unittest.TestCase):
    def test_independent_pratt_grammar_matches_python_ast_precedence(self):
        cases = {
            "-2**2": "-4", "(-2)**2": "4", "2**3**2": "512",
            "2**-3": "1/8", "+2**-2": "1/4",
            "-(1/3+1/6)": "-1/2",
            "1--2": "3", "3/-2": "-3/2",
            "1/(1+2)": "1/3", "0**0": "1",
            "000.125+0.375": "1/2",
            ".125+0.125": "1/4",
            "2.50*0.4": "1",
            "(1+2)*(3+4)": "21",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression), expected)
                self.assertEqual(reference_calculate(expression), expected)

    def test_decimal_literals_are_exact_not_float_approximations(self):
        for literal in ("0.1", ".125", "1.25", "0.0000000000001",
                        "100.0", "3.1415926535897932384626433832"):
            with self.subTest(literal=literal):
                ref = str(Fraction(Decimal(literal)))
                self.assertEqual(calculate(literal), ref)
                self.assertEqual(reference_calculate(literal), ref)

    def test_seeded_differential_expression_corpus(self):
        rng = random.Random(0xC0505)

        def expr(depth=0):
            if depth >= 3 or rng.randrange(5) == 0:
                return rng.choice(("0", "1", "2", "7", "-3", "9/11",
                                   "0.125", "1.20", "17/3", ".5"))
            if rng.randrange(6) == 0:
                return "-(" + expr(depth+1) + ")"
            a, b = expr(depth+1), expr(depth+1)
            op = rng.choice(("+", "-", "*", "/"))
            return "(" + a + op + b + ")"

        valid = 0
        rejected = 0
        for i in range(600):
            expression = expr()
            with self.subTest(case=i, expression=expression):
                try:
                    expected = reference_calculate(expression)
                except ValueError:
                    with self.assertRaises(ValueError):
                        calculate(expression)
                    rejected += 1
                    continue
                actual = calculate(expression)
                self.assertEqual(actual, expected)
                self.assertEqual(str(Fraction(actual)), actual)
                valid += 1
        self.assertGreater(valid, 250)
        self.assertGreater(rejected, 0)

    def test_unsupported_unicode_control_and_code_syntax_rejected(self):
        rejected = (
            "1\n+2", "1\r+2", "1\x00+2", "1;2", "1#comment",
            "１+1", "١+1", "1+𝟚", "1+π", "1\\+2", "1e3", "1_000",
            "0xff", "True", "[1]", "1%2", "1//2",
            "__import__('os')", "().__class__", "1 or 2",
        )
        for expression in rejected:
            with self.subTest(expression=repr(expression)):
                with self.assertRaises(ValueError):
                    calculate(expression)
                with self.assertRaises(ValueError):
                    reference_calculate(expression)

    def test_exact_bounds_prevent_huge_intermediates_or_exponents(self):
        for expression in (
            "2**100000", "0**-1", "2**(2**16)",
            "9"*40+"**16", "1/"+"9"*41,
            "2**0.5", "-2**-18",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    calculate(expression)
                with self.assertRaises(ValueError):
                    reference_calculate(expression)

    def test_reference_is_not_second_model_visible_operation(self):
        manifest = Calculator().manifest()
        self.assertEqual(tuple(op.name for op in manifest.operations), ("calc.rational",))
        self.assertEqual(calculate("1/3 + 1/6"), "1/2")

    def test_untrusted_worker_still_unavailable(self):
        from cognitum.worker_wire import start_isolated_worker, admission_status
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(calculator_verification=True)


class C05ProtobufWireVerification(unittest.TestCase):
    def setUp(self):
        try:
            from cognitum.proto import capability_pb2
            from cognitum import protobuf_codec
        except ImportError:
            self.skipTest("Optional [proto] dependency not installed")
        self.pb = capability_pb2
        self.codec = protobuf_codec

    def test_known_request_field_shadowing_rejected(self):
        wire = self.codec.encode_rational_request("1+2").payload
        self.assertEqual(self.codec.decode_rational_request(
            self.codec.RATIONAL_REQUEST_TYPE, wire), "1+2")
        # Known singular expression field repeated: normally last wins.
        for invalid in (wire + b"\x0a\x013", b"\x0a\x013" + wire):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.codec.decode_rational_request(
                        self.codec.RATIONAL_REQUEST_TYPE, invalid)

    def test_known_result_field_shadowing_and_nested_unknown_rejected(self):
        output = self.pb.CalculateRationalResult(value="1/2")
        output.evidence.add(kind="computation", ref="req1")
        output.limitations.append("intent_not_verified")
        wire = output.SerializeToString(deterministic=True)
        self.assertEqual(
            self.codec.decode_success(
                "calc.rational", self.codec.RATIONAL_RESULT_TYPE, wire,
                request_id="req1", correlation_id="turn1").value.value,
            "1/2",
        )
        mutated = wire + b"\x0a\x013"
        with self.assertRaises(ValueError):
            self.codec.decode_success(
                "calc.rational", self.codec.RATIONAL_RESULT_TYPE, mutated,
                request_id="req1", correlation_id="turn1",
            )
        # Unknown fields buried in nested EvidenceRef must be rejected too.
        output.evidence[0].ref = "req1"
        nested = output.evidence[0].SerializeToString(deterministic=True)
        nested += b"\x98\x06\x01"
        # Create an outer result that includes a mutated nested evidence field.
        bad = self.pb.CalculateRationalResult(value="1/2")
        bad.limitations.append("intent_not_verified")
        raw = bad.SerializeToString(deterministic=True)
        raw += b"\x12" + bytes([len(nested)]) + nested
        with self.assertRaises(ValueError):
            self.codec.decode_success(
                "calc.rational", self.codec.RATIONAL_RESULT_TYPE, raw,
                request_id="req1", correlation_id="turn1",
            )

    def test_native_exact_output_preserves_intent_limitation(self):
        from cognitum.capability_results import CapabilityResult, ExactRational, EvidenceRef
        value = CapabilityResult(
            request_id="req1", correlation_id="turn1",
            operation="calc.rational", operation_schema_version="1.0.0",
            status="completed", value=ExactRational(calculate("1/3+1/6")),
            evidence=(EvidenceRef("computation", "req1"),),
            limitations=("intent_not_verified",),
        )
        emitted = self.codec.encode_result(value)
        reconstructed = self.codec.decode_success(
            "calc.rational", emitted.type_url, emitted.payload,
            request_id="req1", correlation_id="turn1")
        self.assertEqual(reconstructed, value)


if __name__ == "__main__":
    unittest.main()
