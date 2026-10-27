"""C03 evaluation is deterministic P2 component smoke, NOT Lu/model A/B evidence."""
import hashlib
import subprocess
import sys
import unittest

try:
    from cognitum.eval_protobuf import (
        EVALUATION_REPORT_TYPE_URL, EVALUATION_SUITE_TYPE_URL,
        MAX_FRAME, decode_component_report, decode_suite,
        encode_component_report, encode_suite, frozen_suite,
        run_component_smoke,
    )
    from cognitum.proto import evaluation_pb2 as pb
except ModuleNotFoundError:
    raise unittest.SkipTest("optional Cognitum [proto] runtime not installed")


class C03EvaluationContractTests(unittest.TestCase):
    def test_native_binary_proto_and_canonical_roundtrip(self):
        suite_frame = encode_suite()
        report_frame = encode_component_report()
        self.assertNotEqual(suite_frame[:1], b"{")
        self.assertNotEqual(report_frame[:1], b"{")
        self.assertLessEqual(len(suite_frame), MAX_FRAME)
        self.assertLessEqual(len(report_frame), MAX_FRAME)
        self.assertEqual(decode_suite(suite_frame), frozen_suite())
        self.assertEqual(decode_component_report(report_frame),
                         run_component_smoke(suite_frame))
        self.assertEqual(pb.DESCRIPTOR.package, "cognitum.eval.v1")
        self.assertEqual(EVALUATION_SUITE_TYPE_URL,
                         "type.googleapis.com/" + pb.EvaluationSuite.DESCRIPTOR.full_name)
        self.assertEqual(EVALUATION_REPORT_TYPE_URL,
                         "type.googleapis.com/" + pb.EvaluationReport.DESCRIPTOR.full_name)

    def test_report_is_reproducible_byte_for_byte(self):
        self.assertEqual(encode_suite(), encode_suite())
        self.assertEqual(encode_component_report(), encode_component_report())
        first = decode_component_report(encode_component_report())
        self.assertEqual(first.suite_sha256, hashlib.sha256(encode_suite()).hexdigest())

    def test_both_correct_arithmetic_and_denied_syntax_are_scored(self):
        suite = frozen_suite()
        report = run_component_smoke(encode_suite())
        self.assertEqual(report.total, 10)
        self.assertEqual(report.passed, 10)
        self.assertEqual(len(report.cases), len(suite.cases))
        outcomes = {x.case_id: x for x in report.cases}
        self.assertEqual(outcomes["decimal"].observed_rational, "3/10")
        self.assertEqual(outcomes["fraction"].verdict, pb.EXACT_MATCH)
        self.assertEqual(outcomes["zero_division"].verdict, pb.EXPECTED_REJECTION)
        self.assertEqual(outcomes["unsafe_function"].error_code, "invalid_expression")
        self.assertEqual(outcomes["unknown_symbol"].observed_rational, "")

    def test_model_arm_matrix_predeclared_but_none_executed(self):
        suite = frozen_suite()
        report = decode_component_report(encode_component_report())
        arms = (pb.HOST_ONLY, pb.CONVENTIONAL_TOOL,
                pb.COGNITUM_SINGLE, pb.COGNITUM_COMPOSITION)
        self.assertEqual(tuple(suite.planned_host_arms), arms)
        self.assertEqual(tuple(report.unexecuted_host_arms), arms)
        self.assertEqual(suite.tier, pb.COMPONENT_SYNTHETIC)
        self.assertEqual(report.tier, pb.COMPONENT_SYNTHETIC)
        self.assertFalse(report.model_arms_executed)
        self.assertFalse(report.promotion_evidence)
        self.assertEqual(report.scope_code, "trusted_component_smoke_only")
        self.assertFalse(suite.contains_real_user_data)

    def test_no_promotion_model_arms_or_extra_user_inputs_permitted(self):
        mutants = (
            lambda s: setattr(s, "tier", pb.LU_MODEL_TASK),
            lambda s: setattr(s, "contains_real_user_data", True),
            lambda s: s.cases.add(case_id="new_user_prompt", expression="SECRET", expected_behavior=pb.EXACT_RATIONAL),
            lambda s: setattr(s.cases[0], "expected_rational", "0"),
            lambda s: setattr(s.cases[0], "expression", "1/0"),
            lambda s: s.planned_host_arms.append(pb.HOST_ONLY),
            lambda s: s.cases.pop(),
            lambda s: setattr(s, "schema_version", 999),
        )
        for i, fn in enumerate(mutants):
            candidate = pb.EvaluationSuite()
            candidate.CopyFrom(frozen_suite())
            fn(candidate)
            with self.subTest(change=i), self.assertRaises(ValueError):
                decode_suite(candidate.SerializeToString(deterministic=True))

    def test_report_forgery_missing_wrong_and_overclaiming_results_rejected(self):
        changes = (
            lambda r: setattr(r, "promotion_evidence", True),
            lambda r: setattr(r, "model_arms_executed", True),
            lambda r: setattr(r, "tier", pb.LU_MODEL_TASK),
            lambda r: setattr(r, "suite_sha256", "a" * 64),
            lambda r: setattr(r, "total", 999),
            lambda r: setattr(r, "passed", 999),
            lambda r: r.unexecuted_host_arms.pop(),
            lambda r: r.cases.pop(),
            lambda r: setattr(r.cases[0], "observed_rational", "wrong"),
            lambda r: setattr(r.cases[0], "verdict", pb.INCORRECT_RESULT),
            lambda r: setattr(r, "scope_code", "model_verified"),
        )
        for i, change in enumerate(changes):
            result = pb.EvaluationReport()
            result.CopyFrom(run_component_smoke(encode_suite()))
            change(result)
            with self.subTest(change=i), self.assertRaises(ValueError):
                decode_component_report(result.SerializeToString(deterministic=True))

    def test_unknown_fields_duplicate_scalar_tags_and_malformed_frames_rejected(self):
        for raw in (b"", b"\x00", b"\x0a\xff",
                    b"x" * (MAX_FRAME + 1),
                    encode_suite() + b"\x98\x06\x01",
                    encode_suite() + b"\x08\x01",
                    "text", None):
            with self.subTest(kind=str(raw)[:20]), self.assertRaises(ValueError):
                decode_suite(raw)
        for raw in (b"", b"\x00", b"\x0a\xff",
                    b"x" * (MAX_FRAME + 1),
                    encode_component_report() + b"\x98\x06\x01",
                    encode_component_report() + b"\x08\x01",
                    "text", None):
            with self.subTest(kind=str(raw)[:20]), self.assertRaises(ValueError):
                decode_component_report(raw)

    def test_result_contract_has_no_runtime_grants_or_fake_timings(self):
        names = {f.name for f in pb.EvaluationReport.DESCRIPTOR.fields}
        self.assertTrue(names.isdisjoint({
            "permissions", "grants", "sandbox_verified", "host_approved",
            "fake_latency_ms", "prompt", "user_id", "model_weights",
        }))
        self.assertEqual(pb.EvaluationReport.DESCRIPTOR.fields_by_name["total"].number, 6)

    def test_cli_binary_default_and_text_check_boundary(self):
        raw = subprocess.run(
            [sys.executable, "tools/run_c03_smoke.py"],
            capture_output=True, check=True,
        ).stdout
        self.assertEqual(decode_component_report(raw).total, 10)
        human = subprocess.run(
            [sys.executable, "tools/run_c03_smoke.py", "--check"],
            text=True, capture_output=True, check=True,
        ).stdout
        self.assertIn("10/10", human)
        self.assertIn("promotion evidence: false", human)

    def test_does_not_modify_c02_worker_admission(self):
        from cognitum.worker_wire import admission_status, start_isolated_worker
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(eval_report=encode_component_report())

    def test_case_oracle_is_canonical_and_synthetic(self):
        from cognitum.capability_results import ExactRational
        data = frozen_suite()
        ids = [x.case_id for x in data.cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in data.cases:
            self.assertLessEqual(len(case.expression), 256)
            if case.expected_behavior == pb.EXACT_RATIONAL:
                self.assertEqual(ExactRational(case.expected_rational).value,
                                 case.expected_rational)
            else:
                self.assertEqual(case.expected_rational, "")


if __name__ == "__main__":
    unittest.main()
