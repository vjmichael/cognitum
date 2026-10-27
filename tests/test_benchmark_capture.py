"""C03 benchmark capture wire-contract tests: synthetic metadata, no Lu run."""
from hashlib import sha256
import unittest

try:
    from cognitum.proto import benchmark_pb2 as pb
    from cognitum.benchmark_capture import (
        ARM_ORDER, PLAN_TYPE_URL, CAPTURE_TYPE_URL,
        encode_plan, decode_plan, encode_capture, decode_capture,
        empty_capture_template, expected_schedule, validate_plan,
        validate_capture,
    )
except ModuleNotFoundError:
    raise unittest.SkipTest("optional protobuf runtime absent")


# TEST-ONLY fake SHA values. These are not Lu/model/hardware provenance.
def fake_sha(ch):
    return ch * 64


def example_plan(*, runnable=False, repeats=4):
    p = pb.BenchmarkPlan(
        schema_version=1, plan_id="fixture-benchmark-unrun-v1",
        dataset_id="public-fixture-v1", dataset_sha256=fake_sha("a"),
        scoring_rubric_sha256=fake_sha("b"), lu_build_sha256=fake_sha("c"),
        model_artifact_sha256=fake_sha("d"), model_id="EXAMPLE-MODEL-NOT-LOADED",
        backend_id="unconfigured-lu-adapter",
        quantization_id="example-quantization",
        host_policy_sha256=fake_sha("e"), platform_id="test-runner",
        hardware_profile_id="example-no-real-hardware",
        model_context_sha256=fake_sha("f"),
        includes_raw_user_content=False,
    )
    p.inference.temperature_milli = 0
    p.inference.top_p_ppm = 1_000_000
    p.inference.max_output_tokens = 512
    p.inference.context_window_tokens = 4096
    p.inference.tool_budget = 4
    p.inference.repeats = repeats
    p.inference.seed = 25
    for index, arm in enumerate(ARM_ORDER):
        x = p.arms.add(
            arm=arm, readiness=pb.HOST_APPROVED_RUNNABLE if runnable else pb.NOT_RUNNABLE,
            comparator_id=("host", "conventional", "candidate", "composition")[index],
            comparator_build_sha256=fake_sha("1"),
            tool_catalog_sha256=fake_sha(str(index+1)),
            unavailable_reason_code="" if runnable else "lu_ce_bridge_missing",
        )
        if arm == pb.COGNITUM_SINGLE:
            x.enabled_native_tool_ids.append("cognitum.calc.rational")
        if arm == pb.COGNITUM_COMPOSITION:
            x.enabled_native_tool_ids.extend((
                "cognitum.calc.rational", "cognitum.future.math"))
        if arm == pb.CONVENTIONAL_TOOL:
            x.enabled_native_tool_ids.append("conventional.math")
    for t in ("arithmetic-public", "abstention-public"):
        p.tasks.add(task_id=t, task_sha256=fake_sha("8"),
                    expected_tool_use=(pb.TOOL_REQUIRED
                                       if t.startswith("arithmetic") else pb.TOOL_NOT_REQUIRED))
    for task_id, arm, repeat_index, seed in expected_schedule(p):
        p.schedule.add(task_id=task_id, arm=arm,
                       repeat_index=repeat_index, seed=seed)
    return p


class BenchmarkPlanTests(unittest.TestCase):
    def test_versioned_native_proto_and_four_arm_pinned_plan(self):
        p = example_plan()
        wire = encode_plan(p)
        self.assertNotEqual(wire[:1], b"{")
        self.assertEqual(decode_plan(wire), p)
        self.assertEqual(pb.DESCRIPTOR.package, "cognitum.benchmark.v1")
        self.assertEqual(PLAN_TYPE_URL,
                         "type.googleapis.com/" + pb.BenchmarkPlan.DESCRIPTOR.full_name)
        self.assertEqual(CAPTURE_TYPE_URL,
                         "type.googleapis.com/" + pb.BenchmarkCapture.DESCRIPTOR.full_name)
        self.assertEqual(len(p.schedule), 2 * 4 * 4)
        self.assertEqual(tuple(a.arm for a in p.arms), ARM_ORDER)
        self.assertEqual(tuple(r.seed for r in p.schedule[:4]), (25,) * 4)

    def test_deterministic_schedule_rotates_arm_order_but_preserves_seed_pairs(self):
        p = example_plan()
        self.assertEqual(tuple(r.arm for r in p.schedule[:4]), ARM_ORDER)
        self.assertEqual(tuple(r.arm for r in p.schedule[4:8]), ARM_ORDER[1:] + ARM_ORDER[:1])
        self.assertEqual(tuple(r.arm for r in p.schedule[8:12]), ARM_ORDER[1:] + ARM_ORDER[:1])
        self.assertEqual(tuple(r.seed for r in p.schedule[8:12]), (26,) * 4)
        self.assertEqual(encode_plan(p), encode_plan(p))

    def test_same_model_and_host_metadata_in_single_plan(self):
        p = example_plan()
        self.assertEqual(len({p.lu_build_sha256}), 1)
        self.assertEqual(len({p.model_artifact_sha256}), 1)
        self.assertEqual(p.inference.temperature_milli, 0)
        self.assertEqual(p.inference.max_output_tokens, 512)
        self.assertEqual(p.inference.repeats, 4)

    def test_missing_model_revision_or_unverified_dataset_hash_fails(self):
        mutants = (
            lambda p: setattr(p, "model_artifact_sha256", ""),
            lambda p: setattr(p, "lu_build_sha256", "0"*64),
            lambda p: setattr(p, "dataset_sha256", "not-a-sha"),
            lambda p: setattr(p, "model_id", "malicious user prompt\nline"),
            lambda p: setattr(p, "includes_raw_user_content", True),
            lambda p: setattr(p, "schema_version", 999),
            lambda p: p.ClearField("inference"),
            lambda p: setattr(p.inference, "top_p_ppm", 0),
            lambda p: setattr(p.inference, "context_window_tokens", 16),
            lambda p: setattr(p.inference, "repeats", 0),
            lambda p: setattr(p.inference, "tool_budget", 1),
        )
        for i, mut in enumerate(mutants):
            p = example_plan()
            mut(p)
            with self.subTest(i=i), self.assertRaises(ValueError):
                encode_plan(p)

    def test_baseline_contamination_and_missing_conventional_comparator_fail(self):
        mutants = (
            lambda p: p.arms[0].enabled_native_tool_ids.append("cognitum.calc.rational"),
            lambda p: p.arms[1].enabled_native_tool_ids.append("cognitum.calc.rational"),
            lambda p: p.arms[2].enabled_native_tool_ids.clear(),
            lambda p: p.arms[3].enabled_native_tool_ids.pop(),
            lambda p: setattr(p.arms[1], "comparator_id", ""),
            lambda p: p.arms[2].enabled_native_tool_ids.append("cognitum.calc.rational"),
            lambda p: p.arms[1].enabled_native_tool_ids.append("malformed name"),
        )
        for i, mut in enumerate(mutants):
            p = example_plan()
            mut(p)
            with self.subTest(i=i), self.assertRaises(ValueError):
                encode_plan(p)

    def test_all_arms_must_declare_availability_and_reason(self):
        for mutation in (
            lambda a: setattr(a, "readiness", pb.ARM_READINESS_UNSPECIFIED),
            lambda a: setattr(a, "readiness", pb.HOST_APPROVED_RUNNABLE),
            lambda a: setattr(a, "unavailable_reason_code", "not_a_recognized_code"),
        ):
            p = example_plan()
            mutation(p.arms[0])
            with self.assertRaises(ValueError):
                validate_plan(p)

    def test_incomplete_reordered_or_mismatched_trials_rejected(self):
        for mut in (
            lambda p: p.schedule.pop(),
            lambda p: setattr(p.schedule[0], "seed", 99),
            lambda p: setattr(p.schedule[0], "arm", pb.COGNITUM_SINGLE),
            lambda p: setattr(p.schedule[0], "task_id", "other"),
            lambda p: setattr(p.schedule[0], "repeat_index", 2),
        ):
            p = example_plan()
            mut(p)
            with self.assertRaises(ValueError):
                encode_plan(p)

    def test_task_metadata_is_hash_only_and_expected_tool_use_is_explicit(self):
        p = example_plan()
        self.assertEqual({t.expected_tool_use for t in p.tasks},
                         {pb.TOOL_REQUIRED, pb.TOOL_NOT_REQUIRED})
        p.tasks[0].expected_tool_use = pb.TOOL_EXPECTATION_UNSPECIFIED
        with self.assertRaises(ValueError):
            validate_plan(p)

    def test_reject_unknown_wire_fields_shadowed_scalar_and_over_size(self):
        wire = encode_plan(example_plan())
        for bad in (b"", b"\x00", b"\x0a\xff", wire+b"\x98\x06\x01",
                    wire+b"\x08\x01", b"x"*65537, "str", None):
            with self.subTest(x=str(bad)[:20]), self.assertRaises(ValueError):
                decode_plan(bad)


class CaptureContractTests(unittest.TestCase):
    def test_notrun_template_is_fully_paired_and_explicitly_unverified(self):
        p = example_plan()
        c = empty_capture_template(p)
        raw = encode_capture(p, c)
        back, review = decode_capture(p, raw)
        self.assertEqual(back, c)
        self.assertEqual(len(back.trials), len(p.schedule))
        self.assertEqual(review.observed_trials, 0)
        self.assertEqual(review.planned_trials, 32)
        self.assertTrue(review.format_valid)
        self.assertFalse(review.model_execution_authenticated)
        self.assertFalse(review.paired_effect_verified)
        self.assertFalse(review.promotion_evidence)
        self.assertFalse(any(row.HasField("resources") for row in back.trials))

    def test_runnable_fixture_can_capture_declared_outcome_and_measured_zero(self):
        # A fabricated TEST fixture exercises the *shape* only, never Lu.
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        row = c.trials[0]
        row.status = pb.COMPLETED
        row.tool_decision = pb.APPROPRIATE
        row.final_grade = pb.CORRECT
        row.answer_sha256 = fake_sha("7")
        row.resources.end_to_end_latency_ms = 0
        row.resources.first_token_latency_ms = 0
        row.resources.attempted_tool_calls = 0
        row.resources.rejected_tool_calls = 0
        review = validate_capture(p, c)
        self.assertEqual(review.observed_trials, 1)
        self.assertFalse(review.model_execution_authenticated)
        self.assertFalse(review.paired_effect_verified)
        self.assertTrue(row.resources.HasField("end_to_end_latency_ms"))
        self.assertFalse(row.resources.HasField("peak_gpu_memory_bytes"))
        self.assertEqual(decode_capture(p, encode_capture(p, c))[0], c)

    def test_failure_denial_timeout_abstention_have_distinct_contracts(self):
        p = example_plan(runnable=True, repeats=1)
        for status, grade, error, answer in (
            (pb.HOST_DENIED, pb.NOT_GRADED, "permission_denied", ""),
            (pb.TIMED_OUT, pb.NOT_GRADED, "trial_timed_out", ""),
            (pb.TOOL_SELECTION_FAILED, pb.NOT_GRADED, "tool_not_selected", ""),
            (pb.ARGUMENT_VALIDATION_FAILED, pb.NOT_GRADED, "invalid_arguments", ""),
            (pb.TOOL_EXECUTION_FAILED, pb.NOT_GRADED, "tool_unavailable", ""),
            (pb.PROVIDER_FAILED, pb.NOT_GRADED, "provider_unavailable", ""),
            (pb.ABSTAINED, pb.APPROPRIATE_ABSTENTION, "", ""),
            (pb.COMPLETED, pb.INCORRECT, "", fake_sha("6")),
        ):
            with self.subTest(status=status):
                c = empty_capture_template(p)
                r = c.trials[0]
                r.status, r.final_grade, r.error_code, r.answer_sha256 = (
                    status, grade, error, answer)
                r.tool_decision = pb.NOT_ASSESSED
                r.resources.end_to_end_latency_ms = 7
                self.assertEqual(validate_capture(p, c).observed_trials, 1)

    def test_unrunnable_arm_cannot_claim_execution(self):
        p = example_plan()
        c = empty_capture_template(p)
        c.trials[0].status = pb.COMPLETED
        c.trials[0].final_grade = pb.CORRECT
        c.trials[0].answer_sha256 = fake_sha("7")
        c.trials[0].resources.end_to_end_latency_ms = 5
        with self.assertRaises(ValueError):
            validate_capture(p, c)

    def test_missing_latency_is_not_equivalent_to_measured_zero(self):
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        r = c.trials[0]
        r.status = pb.COMPLETED
        r.final_grade = pb.CORRECT
        r.tool_decision = pb.APPROPRIATE
        r.answer_sha256 = fake_sha("7")
        r.resources.attempted_tool_calls = 0
        with self.assertRaises(ValueError):
            validate_capture(p, c)
        r.resources.end_to_end_latency_ms = 0
        self.assertTrue(r.resources.HasField("end_to_end_latency_ms"))
        self.assertEqual(validate_capture(p, c).observed_trials, 1)

    def test_rejected_calls_must_be_bounded_by_attempted(self):
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        r = c.trials[0]
        r.status = pb.COMPLETED
        r.final_grade = pb.CORRECT
        r.tool_decision = pb.APPROPRIATE
        r.answer_sha256 = fake_sha("7")
        r.resources.end_to_end_latency_ms = 100
        r.resources.first_token_latency_ms = 101
        with self.assertRaises(ValueError):
            validate_capture(p, c)
        r.resources.first_token_latency_ms = 90
        r.resources.attempted_tool_calls = 1
        r.resources.rejected_tool_calls = 2
        with self.assertRaises(ValueError):
            validate_capture(p, c)
        r.resources.rejected_tool_calls = 1
        self.assertEqual(validate_capture(p, c).observed_trials, 1)

    def test_abstention_cannot_claim_answer_or_success_grade(self):
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        r = c.trials[0]
        r.status = pb.ABSTAINED
        r.final_grade = pb.CORRECT
        r.resources.end_to_end_latency_ms = 55
        with self.assertRaises(ValueError):
            validate_capture(p, c)
        r.final_grade = pb.APPROPRIATE_ABSTENTION
        r.answer_sha256 = fake_sha("7")
        with self.assertRaises(ValueError):
            validate_capture(p, c)

    def test_failure_cannot_contain_graded_output_or_leaked_error_text(self):
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        r = c.trials[0]
        r.status = pb.TOOL_EXECUTION_FAILED
        r.error_code = "SECRET from model\ntraceback..."
        r.resources.end_to_end_latency_ms = 20
        with self.assertRaises(ValueError):
            validate_capture(p, c)
        r.error_code = "tool_unavailable"
        r.final_grade = pb.CORRECT
        with self.assertRaises(ValueError):
            validate_capture(p, c)

    def test_wrong_plan_build_reference_trial_order_or_extra_row_fails(self):
        p = example_plan()
        for mut in (
            lambda c: setattr(c, "plan_sha256", fake_sha("5")),
            lambda c: c.trials.pop(),
            lambda c: c.trials.add(task_id="surprise"),
            lambda c: setattr(c.trials[0], "seed", 777),
            lambda c: setattr(c.trials[0], "arm", pb.COGNITUM_SINGLE),
            lambda c: setattr(c, "claims_production_promotion", True),
            lambda c: setattr(c, "includes_raw_user_content", True),
            lambda c: setattr(c, "schema_version", 2),
            lambda c: setattr(c, "host_collector_id", "malicious prompt\ncredential"),
        ):
            c = empty_capture_template(p)
            mut(c)
            with self.subTest(mut=str(mut)), self.assertRaises(ValueError):
                encode_capture(p, c)

    def test_notrun_must_not_carry_metric_answer_grade_or_errors(self):
        p = example_plan()
        edits = (
            lambda r: setattr(r.resources, "end_to_end_latency_ms", 1),
            lambda r: setattr(r, "error_code", "trial_timed_out"),
            lambda r: setattr(r, "answer_sha256", fake_sha("7")),
            lambda r: setattr(r, "final_grade", pb.CORRECT),
            lambda r: setattr(r, "tool_decision", pb.APPROPRIATE),
        )
        for change in edits:
            c = empty_capture_template(p)
            change(c.trials[0])
            with self.assertRaises(ValueError):
                validate_capture(p, c)

    def test_capture_unknown_wire_fields_duplicate_tags_rejected(self):
        p = example_plan()
        raw = encode_capture(p, empty_capture_template(p))
        for wire in (b"", b"\x00", b"\x0a\xff", raw+b"\x98\x06\x01",
                     raw+b"\x08\x01", "text", None):
            with self.subTest(data=str(wire)[:18]), self.assertRaises(ValueError):
                decode_capture(p, wire)

    def test_contract_does_not_contain_raw_prompts_or_authorization(self):
        sensitive = {"prompt", "transcript", "secret", "token", "permission",
                     "model_weights", "user_id", "sandbox_verified", "consent_granted"}
        fields = {f.name for f in pb.BenchmarkPlan.DESCRIPTOR.fields}
        fields |= {f.name for f in pb.BenchmarkCapture.DESCRIPTOR.fields}
        self.assertTrue(fields.isdisjoint(sensitive))
        resources = pb.ResourceObservation.DESCRIPTOR.fields_by_name
        for key in ("peak_host_ram_bytes", "peak_gpu_memory_bytes",
                    "energy_millijoules", "cost_micro_usd",
                    "input_tokens", "output_tokens", "end_to_end_latency_ms"):
            self.assertTrue(resources[key].has_presence)

    def test_worker_gate_stays_closed_even_for_complete_capture(self):
        from cognitum.worker_wire import admission_status, start_isolated_worker
        p = example_plan(runnable=True, repeats=1)
        c = empty_capture_template(p)
        self.assertFalse(validate_capture(p, c).promotion_evidence)
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(benchmark_capture=encode_capture(p, c))


if __name__ == "__main__":
    unittest.main()
