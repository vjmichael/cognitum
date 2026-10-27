"""Strict Cognitum capability-result contract tests (no Lu host modifications)."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from cognitum.capability_results import (
    CapabilityFailure, CapabilityResult, EvidenceRef, ExactRational,
    NumericalEstimate, RetrievedReferences, from_dict, from_json,
    from_runtime_response,
)
from cognitum.contracts import HostContext, Request, Response
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime


def result(value=None, *, status="completed", evidence=None, failure=None, limitations=None):
    if evidence is None:
        evidence = (EvidenceRef("computation", "test-1"),) if value is not None else ()
    if limitations is None:
        if isinstance(value, ExactRational):
            limitations = ("intent_not_verified",)
        elif isinstance(value, NumericalEstimate):
            limitations = ("intent_not_verified", "uncertainty_unquantified"
                           if value.lower is None else "bounds_not_probabilistic")
        elif isinstance(value, RetrievedReferences):
            limitations = ("retrieval_not_truth", "no_permission_conferred")
        elif status == "validated":
            limitations = ("not_executed",)
        else:
            limitations = ("no_computed_answer",)
    return CapabilityResult(
        request_id="test-1", correlation_id="session-1", operation="calc.rational",
        operation_schema_version="1.0.0", status=status, value=value,
        evidence=evidence, failure=failure, limitations=limitations,
    )


class ResultContractTests(unittest.TestCase):
    def test_frozen_cross_component_result_fixtures(self):
        fixture_path = Path(__file__).parent / "fixtures" / "capability_results_v1.json"
        samples = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(set(samples), {"exact", "numerical", "retrieval",
                                        "denied", "validated_only", "timeout"})
        for name, data in samples.items():
            with self.subTest(sample=name):
                self.assertEqual(from_dict(data).to_dict(), data)
                self.assertEqual(from_json(json.dumps(data)).to_dict(), data)

    def test_exact_rational_roundtrip_with_assumption_limit(self):
        x = result(ExactRational("1/3"))
        self.assertEqual(x.assurance, "exact_arithmetic")
        self.assertEqual(x.interpretation, "assumption_bound")
        self.assertIn("intent_not_verified", x.to_dict()["limitations"])
        self.assertEqual(from_dict(x.to_dict()), x)
        self.assertEqual(from_json(json.dumps(x.to_dict())), x)

    def test_exact_rejects_noncanonical_or_unbounded(self):
        for raw in ("", "2/4", "1/1", "01", "-0", "0/2", "1/0", "1/-2",
                    "1.0", "NaN", "Infinity", "1e4", "1/2/3", "1" * 1100):
            with self.subTest(raw=raw[:24]), self.assertRaises(ValueError):
                ExactRational(raw)
        with self.assertRaises(ValueError):
            ExactRational("2" * 400)

    def test_numerical_estimate_unquantified_no_confidence_claim(self):
        v = NumericalEstimate("0.0012", "kan.portable.v1")
        r = result(v, evidence=(EvidenceRef("checkpoint", "sha256:abc"),))
        self.assertEqual(r.assurance, "numerical")
        self.assertIn("uncertainty_unquantified", r.to_dict()["limitations"])
        self.assertEqual(from_dict(r.to_dict()), r)

    def test_numerical_interval_not_a_confidence_interval(self):
        v = NumericalEstimate("1.2", "spline.v1", "1.1", "1.4")
        r = result(v)
        self.assertIn("bounds_not_probabilistic", r.to_dict()["limitations"])
        self.assertNotIn("confidence", json.dumps(r.to_dict()))
        self.assertEqual(from_json(json.dumps(r.to_dict())), r)

    def test_numeric_invalid_bounds_and_values(self):
        tests = [
            ("NaN", None, None), ("Infinity", None, None),
            ("1", "0", None), ("1", "2", "3"),
            ("1", "3", "0"), ("1", "0", "0.9"),
            ("1e9999", None, None), ("1" * 81, None, None),
        ]
        for v, lower, upper in tests:
            with self.subTest(v=v[:12], lower=lower, upper=upper), self.assertRaises(ValueError):
                NumericalEstimate(v, "kan.v1", lower, upper)

    def test_numeric_no_coercion(self):
        for value in (1, True, None, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NumericalEstimate(value, "kan.v1")
        with self.assertRaises(ValueError):
            NumericalEstimate("1", "with spaces")

    def test_retrieval_refs_are_not_truth_or_authorization(self):
        v = RetrievedReferences(("item1", "item2"), "rev7", "rev7")
        r = result(v, evidence=(EvidenceRef("source_snapshot", "rev7"),))
        self.assertEqual(r.assurance, "heuristic")
        self.assertEqual(set(r.limitations), {"retrieval_not_truth", "no_permission_conferred"})
        self.assertEqual(from_dict(r.to_dict()), r)

    def test_retrieval_rejects_stale_empty_duplicate_or_unbounded(self):
        invalid = [
            ((), "v1", "v1"), (("a", "a"), "v1", "v1"),
            (("a",), "v1", "v2"), (("a",) * 65, "v1", "v1"),
            (("raw secret token",), "v1", "v1"),
        ]
        for candidates, source, indexed in invalid:
            with self.subTest(count=len(candidates)), self.assertRaises(ValueError):
                RetrievedReferences(candidates, source, indexed)
        with self.assertRaises(ValueError):
            RetrievedReferences(["a"], "v1", "v1")

    def test_no_completed_result_without_evidence(self):
        with self.assertRaises(ValueError):
            result(ExactRational("2"), evidence=())
        with self.assertRaises(ValueError):
            result(ExactRational("2"), failure=CapabilityFailure("plugin_error"))

    def test_completed_requires_correct_epistemic_limitations(self):
        with self.assertRaises(ValueError):
            result(ExactRational("1"), limitations=("no_computed_answer",))
        with self.assertRaises(ValueError):
            result(NumericalEstimate("1", "m.v1"), limitations=("intent_not_verified",))
        with self.assertRaises(ValueError):
            result(RetrievedReferences(("a",), "x", "x"),
                   limitations=("retrieval_not_truth",))

    def test_failed_and_validated_never_carry_value_or_evidence(self):
        with self.assertRaises(ValueError):
            result(ExactRational("2"), status="denied", failure=CapabilityFailure("permission_denied"))
        with self.assertRaises(ValueError):
            result(None, status="unavailable", failure=CapabilityFailure("capability_unavailable"),
                   evidence=(EvidenceRef("computation", "test-1"),))
        with self.assertRaises(ValueError):
            result(None, status="validated", evidence=(EvidenceRef("computation", "test-1"),))
        with self.assertRaises(ValueError):
            result(None, status="validated", failure=CapabilityFailure("plugin_error"))
        self.assertIsNone(result(status="validated").to_dict()["value"])

    def test_failures_are_typed_no_exception_text(self):
        r = result(status="denied", failure=CapabilityFailure("permission_denied"))
        self.assertEqual(r.to_dict()["failure"], {"code": "permission_denied", "retryable": False})
        self.assertIsNone(r.to_dict()["value"])
        self.assertEqual(r.assurance, "unverified")
        self.assertEqual(from_dict(r.to_dict()), r)
        for error in ("SECRET: stacktrace", "unknown", "", 55):
            with self.subTest(error=error), self.assertRaises(ValueError):
                CapabilityFailure(error)

    def test_failure_code_must_match_status_and_retryability(self):
        with self.assertRaises(ValueError):
            result(status="denied", failure=CapabilityFailure("plugin_error"))
        with self.assertRaises(ValueError):
            result(status="invalid_input", failure=CapabilityFailure("invalid_request", True))
        with self.assertRaises(ValueError):
            result(status="unavailable", failure=CapabilityFailure("capability_unavailable", "true"))
        self.assertEqual(from_dict(result(status="timed_out",
                              failure=CapabilityFailure("plugin_timed_out", True)).to_dict()).status,
                         "timed_out")

    def test_reject_extra_nested_unknown_schema_keys(self):
        good = result(ExactRational("1/3")).to_dict()
        for outer in ("grant", "model_instruction", "payload"):
            tampered = dict(good, **{outer: "SECRET"})
            with self.subTest(outer=outer), self.assertRaises(ValueError):
                from_dict(tampered)
        tampered = json.loads(json.dumps(good))
        tampered["value"]["role"] = "system"
        with self.assertRaises(ValueError):
            from_dict(tampered)
        tampered = json.loads(json.dumps(good))
        tampered["evidence"][0]["content"] = "SECRET"
        with self.assertRaises(ValueError):
            from_dict(tampered)

    def test_forged_assurance_or_interpretation_rejected(self):
        good = result(NumericalEstimate("1.1", "kan.v1")).to_dict()
        for k, v in (("assurance", "exact_arithmetic"), ("interpretation", "verified")):
            with self.subTest(k=k), self.assertRaises(ValueError):
                from_dict(dict(good, **{k: v}))
        with self.assertRaises(ValueError):
            from_dict(dict(good, schema_version="999.0.0"))

    def test_duplicate_json_keys_and_bogus_json_rejected(self):
        source = json.dumps(result(ExactRational("1")).to_dict())
        source = source.replace('"status": "completed"', '"status": "denied", "status": "completed"')
        with self.assertRaises(ValueError):
            from_json(source)
        with self.assertRaises((TypeError, ValueError)):
            from_json(None)
        with self.assertRaises(json.JSONDecodeError):
            from_json("{")

    def test_json_input_size_and_optional_presence_are_bounded(self):
        with self.assertRaises(ValueError):
            from_json(" " * (16 * 1024 + 1))
        good = result(NumericalEstimate("1", "kan.v1")).to_dict()
        del good["value"]["lower"]
        with self.assertRaises(ValueError):
            from_dict(good)
        good = result(NumericalEstimate("1", "kan.v1")).to_dict()
        good["value"]["upper"] = None
        self.assertEqual(from_dict(good).value.upper, None)

    def test_provenance_duplication_ref_shape_and_caps(self):
        with self.assertRaises(ValueError):
            EvidenceRef("untrusted_model", "secret")
        with self.assertRaises(ValueError):
            EvidenceRef("computation", "raw user statement with spaces")
        e = EvidenceRef("computation", "ref1")
        with self.assertRaises(ValueError):
            result(ExactRational("1"), evidence=(e, e))
        with self.assertRaises(ValueError):
            result(ExactRational("1"), evidence=(e,) * 33)

    def test_integrates_with_existing_exact_calculator_without_changing_response(self):
        reg = Registry()
        reg.install(Calculator, enabled=True)
        reg.nominate("calc", "reference_calc")
        response = Runtime(reg).call(
            Request("test-1", "session-1", "calc.rational", {"expression": "1/3+1/6"}),
            HostContext("local", "local-user"))
        original = response.to_dict()
        typed = from_runtime_response(response)
        self.assertEqual(typed.value, ExactRational("1/2"))
        self.assertEqual(typed.assurance, "exact_arithmetic")
        self.assertEqual(typed.evidence, (EvidenceRef("computation", "test-1"),))
        self.assertEqual(typed.to_dict()["interpretation"], "assumption_bound")
        self.assertEqual(response.to_dict(), original)

    def test_legacy_disabled_and_invalid_input_convert_without_fake_success(self):
        response = Response("test-1", "session-1", "calc.rational", "unavailable",
                            limitations=["Unavailable"])
        typed = from_runtime_response(response)
        self.assertEqual(typed.failure.code, "capability_unavailable")
        self.assertFalse(typed.failure.retryable)  # disabled extension is not a transient failure
        self.assertIsNone(typed.value)
        response = replace(response, execution_status="invalid_input", error="invalid_request")
        typed = from_runtime_response(response)
        self.assertEqual(typed.failure.code, "invalid_request")
        self.assertIsNone(typed.value)

    def test_legacy_dry_run_and_denial_convert_without_value(self):
        base = Response("test-1", "session-1", "calc.rational", "validated",
                        limitations=["Schema checked"])
        self.assertIsNone(from_runtime_response(base).value)
        self.assertEqual(from_runtime_response(base).limitations, ("not_executed",))
        denied = replace(base, execution_status="denied", error="permission_denied")
        self.assertEqual(from_runtime_response(denied).failure.code, "permission_denied")

    def test_legacy_timeout_and_failure_convert_without_value(self):
        base = Response("test-1", "session-1", "calc.rational", "timed_out",
                        error="plugin_timed_out")
        self.assertTrue(from_runtime_response(base).failure.retryable)
        broken = replace(base, execution_status="error",
                         error="invalid_plugin_response_or_worker_failure")
        self.assertEqual(from_runtime_response(broken).status, "error")

    def test_legacy_unknown_success_does_not_invent_assurance(self):
        base = Response("test-1", "session-1", "unknown.op", "completed",
                        result={"value": "1"}, outcome={"kind": "value"},
                        assurance="numerical",
                        interpretation={"level": "assumption_bound"},
                        evidence=[{"kind": "computation", "ref": "test-1"}])
        with self.assertRaises(ValueError):
            from_runtime_response(base)
        forged = replace(base, operation="calc.rational", assurance="exact_arithmetic",
                         evidence=[{"kind": "computation", "ref": "fake"}])
        with self.assertRaises(ValueError):
            from_runtime_response(forged)

    def test_bad_runtime_success_and_error_do_not_cross_bridge(self):
        completed = Response("test-1", "session-1", "calc.rational", "completed",
                             result={"value": "1/0"}, outcome={"kind": "value"},
                             assurance="exact_arithmetic",
                             interpretation={"level": "assumption_bound"},
                             evidence=[{"kind": "computation", "ref": "test-1"}])
        with self.assertRaises(ValueError):
            from_runtime_response(completed)
        failed = replace(completed, execution_status="error", result=None)
        with self.assertRaises(ValueError):
            from_runtime_response(failed)


if __name__ == "__main__":
    unittest.main()
