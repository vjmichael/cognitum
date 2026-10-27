"""C04 signed Lu host-collector receipt shape tests, NOT actual Lu telemetry."""
from hashlib import sha256
import unittest

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cognitum.proto import benchmark_pb2 as bp, collector_pb2 as cp
    from cognitum.benchmark_capture import (
        encode_plan, encode_capture, empty_capture_template, expected_schedule,
        ARM_ORDER,
    )
    from cognitum.lu_collector_receipt import (
        verify_host_collector_receipt, DOMAIN, MAX_SIGNED_BYTES,
        COLLECTOR_RECEIPT_TYPE_URL, SIGNED_COLLECTOR_RECEIPT_TYPE_URL,
    )
except ImportError:
    raise unittest.SkipTest("optional security/protobuf dependencies unavailable")


NOW = 1_800_000_000_000
NONCE = "a" * 64
KEY_ID = "lu-test-collector-key"
COLLECTOR = "lu-trusted-collector-proposal"
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def sample_plan():
    """Fictional TEST-ONLY plan with no actual model or Lu binaries."""
    p = bp.BenchmarkPlan(
        schema_version=1, plan_id="fixture-lu-plan", dataset_id="public-fixture",
        dataset_sha256="1"*64, scoring_rubric_sha256="2"*64,
        lu_build_sha256=SHA_B, model_artifact_sha256=SHA_C,
        model_id="EXAMPLE-model-not-loaded", backend_id="test-backend",
        quantization_id="example-q", host_policy_sha256="3"*64,
        model_context_sha256="4"*64, platform_id="test-platform",
        hardware_profile_id="test-hardware", includes_raw_user_content=False,
    )
    p.inference.temperature_milli = 0
    p.inference.top_p_ppm = 1_000_000
    p.inference.max_output_tokens = 128
    p.inference.context_window_tokens = 4096
    p.inference.tool_budget = 4
    p.inference.repeats = 1
    p.inference.seed = 77
    for idx, arm in enumerate(ARM_ORDER):
        a = p.arms.add(
            arm=arm, readiness=bp.NOT_RUNNABLE,
            comparator_id=("baseline", "sqlite", "cognitum-single", "cognitum-combo")[idx],
            comparator_build_sha256="5"*64, tool_catalog_sha256=str(idx+6)*64,
            unavailable_reason_code="lu_ce_bridge_missing",
        )
        if arm == bp.CONVENTIONAL_TOOL:
            a.enabled_native_tool_ids.append("conventional.lookup")
        elif arm == bp.COGNITUM_SINGLE:
            a.enabled_native_tool_ids.append("cognitum.calc.rational")
        elif arm == bp.COGNITUM_COMPOSITION:
            a.enabled_native_tool_ids.extend(
                ("cognitum.calc.rational", "cognitum.future.math"))
    p.tasks.add(task_id="synthetic-task", task_sha256="e"*64,
                expected_tool_use=bp.TOOL_REQUIRED)
    for task_id, arm, repeat, seed in expected_schedule(p):
        p.schedule.add(task_id=task_id, arm=arm, repeat_index=repeat, seed=seed)
    return p


def make_receipt(pframe, cframe):
    c = bp.BenchmarkCapture.FromString(cframe)
    return cp.CollectorReceipt(
        schema_version=1,
        plan_sha256=sha256(pframe).hexdigest(),
        capture_sha256=sha256(cframe).hexdigest(),
        challenge_nonce=NONCE,
        collector_id=COLLECTOR,
        collector_build_sha256=SHA_D,
        lu_build_sha256=SHA_B,
        model_artifact_sha256=SHA_C,
        run_id=c.capture_id,
        collected_at_unix_ms=NOW,
        reported_observed_trials=0,
        declared_source=cp.LU_HOST_DECLARED,
        contains_raw_user_data=False,
        execution_security_verified=False,
    )


def sign(receipt, private, key_id=KEY_ID):
    serialized = receipt.SerializeToString(deterministic=True)
    return cp.SignedCollectorReceipt(
        serialized_receipt=serialized,
        signature_ed25519=private.sign(DOMAIN + serialized),
        signing_key_id=key_id,
    ).SerializeToString(deterministic=True)


class CollectorReceiptTests(unittest.TestCase):
    def setUp(self):
        # Never store production signing keys in Cognitum or unit tests.
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.plan = sample_plan()
        self.plan_frame = encode_plan(self.plan)
        self.capture = empty_capture_template(self.plan)
        self.capture.host_collector_id = COLLECTOR
        self.capture.host_collector_build_sha256 = SHA_D
        self.capture_frame = encode_capture(self.plan, self.capture)
        self.receipt = make_receipt(self.plan_frame, self.capture_frame)

    def check(self, signed=None, *, plan=None, capture=None, **kwargs):
        args = dict(
            trusted_public_key=self.public,
            expected_signing_key_id=KEY_ID,
            expected_collector_id=COLLECTOR,
            expected_collector_build_sha256=SHA_D,
            expected_lu_build_sha256=SHA_B,
            expected_model_artifact_sha256=SHA_C,
            expected_plan_sha256=sha256(self.plan_frame).hexdigest(),
            expected_challenge_nonce=NONCE,
            now_unix_ms=NOW,
        )
        args.update(kwargs)
        return verify_host_collector_receipt(
            self.plan_frame if plan is None else plan,
            self.capture_frame if capture is None else capture,
            sign(self.receipt, self.key) if signed is None else signed,
            **args,
        )

    def test_binary_protobuf_and_signature_pin_verifies_shape_only(self):
        result = self.check()
        self.assertTrue(result.signature_matches_pinned_key)
        self.assertTrue(result.plan_and_capture_bound)
        self.assertEqual(result.planned_trials, 4)
        self.assertEqual(result.reported_trials, 0)
        self.assertFalse(result.reported_data_present)
        self.assertFalse(result.collector_runtime_authenticated)
        self.assertFalse(result.metric_provenance_verified)
        self.assertFalse(result.paired_effect_verified)
        self.assertFalse(result.production_promotion_evidence)
        self.assertEqual(cp.DESCRIPTOR.package, "cognitum.benchmark.v1")
        self.assertEqual(COLLECTOR_RECEIPT_TYPE_URL,
                         "type.googleapis.com/"+cp.CollectorReceipt.DESCRIPTOR.full_name)
        self.assertEqual(SIGNED_COLLECTOR_RECEIPT_TYPE_URL,
                         "type.googleapis.com/"+cp.SignedCollectorReceipt.DESCRIPTOR.full_name)

    def test_even_synthetically_observed_trial_is_not_efficacy_proof(self):
        # This is a fabricated local test record, not a Lu model run.
        p = sample_plan()
        for arm in p.arms:
            arm.readiness = bp.HOST_APPROVED_RUNNABLE
            arm.unavailable_reason_code = ""
        pf = encode_plan(p)
        c = empty_capture_template(p)
        c.host_collector_id = COLLECTOR
        c.host_collector_build_sha256 = SHA_D
        row = c.trials[0]
        row.status = bp.COMPLETED
        row.tool_decision = bp.APPROPRIATE
        row.final_grade = bp.CORRECT
        row.answer_sha256 = "7"*64
        row.resources.end_to_end_latency_ms = 0  # TEST-only synthetic number
        cf = encode_capture(p, c)
        receipt = make_receipt(pf, cf)
        receipt.reported_observed_trials = 1
        result = self.check(
            plan=pf, capture=cf, signed=sign(receipt, self.key),
            expected_plan_sha256=sha256(pf).hexdigest(),
        )
        self.assertEqual(result.reported_trials, 1)
        self.assertTrue(result.reported_data_present)
        self.assertFalse(result.collector_runtime_authenticated)
        self.assertFalse(result.metric_provenance_verified)
        self.assertFalse(result.paired_effect_verified)
        self.assertFalse(result.production_promotion_evidence)

    def test_record_claims_no_actual_model_execution(self):
        self.assertTrue(all(row.status == bp.NOT_RUN for row in self.capture.trials))
        self.assertFalse(self.capture.claims_production_promotion)
        self.assertFalse(self.plan.includes_raw_user_content)
        self.assertFalse(self.receipt.execution_security_verified)

    def test_wrong_public_key_signature_and_signing_identity(self):
        other = Ed25519PrivateKey.generate()
        with self.assertRaises(ValueError):
            self.check(trusted_public_key=other.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw))
        with self.assertRaises(ValueError):
            self.check(expected_signing_key_id="unknown")
        with self.assertRaises(ValueError):
            self.check(signed=sign(self.receipt, self.key, key_id="other"))
        env = cp.SignedCollectorReceipt.FromString(sign(self.receipt, self.key))
        env.signature_ed25519 = b"x"*64
        with self.assertRaises(ValueError):
            self.check(signed=env.SerializeToString(deterministic=True))

    def test_plan_capture_are_cryptographically_bound(self):
        other = sample_plan()
        other.model_id = "different"
        with self.assertRaises(ValueError):
            self.check(plan=encode_plan(other))
        alternate = empty_capture_template(self.plan)
        alternate.host_collector_id = COLLECTOR
        alternate.host_collector_build_sha256 = SHA_D
        alternate.capture_id = "modified"
        with self.assertRaises(ValueError):
            self.check(capture=encode_capture(self.plan, alternate))
        for value in (
            {"expected_plan_sha256": "f"*64},
            {"expected_lu_build_sha256": "f"*64},
            {"expected_model_artifact_sha256": "f"*64},
            {"expected_collector_build_sha256": "f"*64},
            {"expected_collector_id": "some-other-collector"},
        ):
            with self.subTest(args=value), self.assertRaises(ValueError):
                self.check(**value)

    def test_challenge_and_freshness_bound_without_claiming_one_use(self):
        with self.assertRaises(ValueError):
            self.check(expected_challenge_nonce="f"*64)
        for now in (NOW + 300_001, NOW - 5001):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.check(now_unix_ms=now)
        # Stateless verifier is NOT protection against replay of a consumed
        # nonce: the external trusted Lu host must record nonce consumption.
        self.assertTrue(self.check().signature_matches_pinned_key)
        self.assertTrue(self.check().signature_matches_pinned_key)

    def test_signed_receipt_tamper_fail_closed(self):
        mutations = (
            lambda x: setattr(x, "plan_sha256", "f"*64),
            lambda x: setattr(x, "capture_sha256", "f"*64),
            lambda x: setattr(x, "challenge_nonce", "f"*64),
            lambda x: setattr(x, "run_id", "other"),
            lambda x: setattr(x, "reported_observed_trials", 1),
            lambda x: setattr(x, "lu_build_sha256", "f"*64),
            lambda x: setattr(x, "model_artifact_sha256", "f"*64),
            lambda x: setattr(x, "collector_build_sha256", "f"*64),
            lambda x: setattr(x, "collector_id", "other"),
            lambda x: setattr(x, "schema_version", 2),
            lambda x: setattr(x, "declared_source", cp.COLLECTOR_SOURCE_UNSPECIFIED),
            lambda x: setattr(x, "contains_raw_user_data", True),
            lambda x: setattr(x, "execution_security_verified", True),
            lambda x: setattr(x, "collected_at_unix_ms", NOW+300_000),
        )
        for i, edit in enumerate(mutations):
            r = cp.CollectorReceipt()
            r.CopyFrom(self.receipt)
            edit(r)
            with self.subTest(i=i), self.assertRaises(ValueError):
                self.check(signed=sign(r, self.key))

    def test_unknown_duplicate_and_malformed_frames(self):
        raw = sign(self.receipt, self.key)
        for bad in (b"", b"\x00", b"\x0a\xff", "text", None,
                    raw+b"\x98\x06\x01", raw+b"\x1a\x01x",
                    b"x"*8193):
            with self.subTest(data=str(bad)[:20]), self.assertRaises(ValueError):
                self.check(signed=bad)
        r = self.receipt.SerializeToString(deterministic=True)
        for bad in (r+b"\x98\x06\x01", r+b"\x08\x01"):
            env = cp.SignedCollectorReceipt(
                serialized_receipt=bad,
                signature_ed25519=self.key.sign(DOMAIN+bad),
                signing_key_id=KEY_ID,
            )
            with self.assertRaises(ValueError):
                self.check(signed=env.SerializeToString(deterministic=True))

    def test_trusted_caller_values_must_be_well_formed(self):
        for override in (
            {"trusted_public_key": b"wrong"},
            {"expected_signing_key_id": ""},
            {"expected_collector_id": "space is forbidden"},
            {"expected_challenge_nonce": "short"},
            {"expected_challenge_nonce": "0"*64},
            {"expected_plan_sha256": ""},
            {"now_unix_ms": True},
        ):
            with self.subTest(inputs=override), self.assertRaises(ValueError):
                self.check(**override)

    def test_no_model_prompt_secrets_or_host_grants_in_receipt(self):
        fields = {f.name for f in cp.CollectorReceipt.DESCRIPTOR.fields}
        self.assertTrue(fields.isdisjoint({
            "prompt", "model_messages", "tool_arguments", "session_token",
            "permission_grant", "user_id", "api_key", "sandbox_verified",
        }))

    def test_c02_worker_launch_remains_forbidden(self):
        from cognitum.worker_wire import start_isolated_worker, admission_status
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(receipt=sign(self.receipt, self.key))


if __name__ == "__main__":
    unittest.main()
