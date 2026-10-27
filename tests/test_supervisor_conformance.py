"""Signed Protobuf conformance receipts: offline FORMAT checks, not OS tests."""
import hashlib
import unittest

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cognitum.supervisor_conformance import (
        DOMAIN, verify_signed_receipt,
    )
except ImportError:
    raise unittest.SkipTest("optional Cognitum [security] extra not installed")

from cognitum.proto import supervisor_acceptance_pb2 as pb
from cognitum.supervisor_acceptance import acceptance_plan, encode_acceptance_plan
from cognitum.worker_wire import admission_status, start_isolated_worker

NOW = 1_800_000_000_000
NONCE = "b" * 64
HOST = "a" * 64
WORKER = "c" * 64
RUNNER = "lu-ci-host-probe"
KEY_ID = "host-key-v1"
DIGEST = "d" * 64


def sample_receipt(*, platform=pb.PLATFORM_WINDOWS, simulation_only=False):
    receipt = pb.SupervisorConformanceReceipt(
        schema_version=1,
        acceptance_plan_sha256=hashlib.sha256(encode_acceptance_plan()).hexdigest(),
        challenge_nonce=NONCE, host_build_sha256=HOST,
        worker_build_sha256=WORKER, platform=platform,
        observed_at_unix_ms=NOW,
        independent_runner_id=RUNNER,
        simulation_only=simulation_only,
    )
    for probe in acceptance_plan().probes:
        if probe.platform in (pb.PLATFORM_ALL, platform):
            receipt.measurements.add(
                probe_id=probe.id, observed=probe.expected,
                attempted=True, evidence_sha256=DIGEST,
            )
    return receipt


def seal(receipt, private, *, key_id=KEY_ID):
    raw = receipt.SerializeToString(deterministic=True)
    envelope = pb.SignedSupervisorReceipt(
        serialized_receipt=raw,
        signature_ed25519=private.sign(DOMAIN + raw),
        signer_key_id=key_id,
    )
    return envelope.SerializeToString(deterministic=True)


def verify(blob, private, **overrides):
    key = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    args = dict(
        trusted_public_key=key,
        expected_signer_key_id=KEY_ID,
        expected_runner_id=RUNNER,
        expected_challenge_nonce=NONCE,
        expected_platform=pb.PLATFORM_WINDOWS,
        expected_host_build_sha256=HOST,
        expected_worker_build_sha256=WORKER,
        now_unix_ms=NOW,
    )
    args.update(overrides)
    return verify_signed_receipt(blob, **args)


class HostConformanceGateTests(unittest.TestCase):
    def setUp(self):
        # Ephemeral test key ONLY. NEVER stored as a host production credential.
        self.private = Ed25519PrivateKey.generate()

    def test_signed_report_can_pass_shape_but_never_os_gate(self):
        # Sample observations are SYNTHETIC, even with simulation_only=False.
        # They prove signature/format verifier behavior, not kernel isolation.
        data = seal(sample_receipt(), self.private)
        review = verify(data, self.private)
        self.assertTrue(review.signed_receipt_valid)
        self.assertTrue(review.reported_probes_complete)
        self.assertEqual(review.platform, "PLATFORM_WINDOWS")
        self.assertFalse(review.os_isolation_verified)
        self.assertFalse(review.production_launch_allowed)

    def test_an_explicit_simulation_flag_is_rejected(self):
        blob = seal(sample_receipt(simulation_only=True), self.private)
        with self.assertRaises(ValueError):
            verify(blob, self.private)

    def test_untrusted_signer_and_mismatched_key_id_rejected(self):
        signed = seal(sample_receipt(), self.private)
        other = Ed25519PrivateKey.generate()
        with self.assertRaises(ValueError):
            verify(signed, other)
        with self.assertRaises(ValueError):
            verify(seal(sample_receipt(), self.private, key_id="untrusted"),
                   self.private)

    def test_signature_covers_every_protobuf_receipt_byte(self):
        frame = pb.SignedSupervisorReceipt.FromString(
            seal(sample_receipt(), self.private))
        frame.serialized_receipt += b"\x98\x06\x01"
        with self.assertRaises(ValueError):
            verify(frame.SerializeToString(deterministic=True), self.private)
        frame = pb.SignedSupervisorReceipt.FromString(
            seal(sample_receipt(), self.private))
        frame.signature_ed25519 = b"bad"
        with self.assertRaises(ValueError):
            verify(frame.SerializeToString(deterministic=True), self.private)

    def test_one_use_nonce_and_build_pins_prevent_cross_session_replay(self):
        blob = seal(sample_receipt(), self.private)
        for overrides in (
            {"expected_challenge_nonce": "e" * 64},
            {"expected_host_build_sha256": "e" * 64},
            {"expected_worker_build_sha256": "e" * 64},
            {"expected_runner_id": "other-host"},
            {"expected_platform": pb.PLATFORM_LINUX},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                verify(blob, self.private, **overrides)
        # Nonce persistence and single-use consumption belong to Lu host.
        self.assertFalse(verify(blob, self.private).production_launch_allowed)

    def test_stale_future_receipts_rejected(self):
        blob = seal(sample_receipt(), self.private)
        for now in (NOW + 300001, NOW - 5001):
            with self.subTest(now=now), self.assertRaises(ValueError):
                verify(blob, self.private, now_unix_ms=now)

    def test_missing_skipped_duplicate_and_wrong_probe_fails(self):
        mutants = (
            lambda r: r.measurements.pop(),
            lambda r: setattr(r.measurements[0], "attempted", False),
            lambda r: setattr(r.measurements[0], "observed", pb.EXPECT_METADATA_ONLY),
            lambda r: setattr(r.measurements[0], "probe_id", "other-probe"),
            lambda r: setattr(r.measurements[0], "evidence_sha256", ""),
            lambda r: setattr(r.measurements[0], "evidence_sha256", "0" * 64),
            lambda r: r.measurements.add(probe_id="extra", attempted=True,
                                         evidence_sha256=DIGEST),
        )
        for i, mutate in enumerate(mutants):
            receipt = sample_receipt()
            mutate(receipt)
            with self.subTest(mutant=i), self.assertRaises(ValueError):
                verify(seal(receipt, self.private), self.private)

    def test_unapproved_plan_hash_version_or_run_identity_rejected(self):
        mutations = (
            lambda r: setattr(r, "schema_version", 2),
            lambda r: setattr(r, "acceptance_plan_sha256", "e" * 64),
            lambda r: setattr(r, "independent_runner_id", "forged-host"),
            lambda r: setattr(r, "platform", pb.PLATFORM_ALL),
            lambda r: setattr(r, "observed_at_unix_ms", 0),
        )
        for i, mutate in enumerate(mutations):
            receipt = sample_receipt()
            mutate(receipt)
            with self.subTest(mutant=i), self.assertRaises(ValueError):
                verify(seal(receipt, self.private), self.private)

    def test_platform_coverage_is_strict_and_distinct(self):
        for platform in (pb.PLATFORM_LINUX, pb.PLATFORM_MACOS):
            receipt = sample_receipt(platform=platform)
            key = self.private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw)
            review = verify_signed_receipt(
                seal(receipt, self.private),
                trusted_public_key=key,
                expected_signer_key_id=KEY_ID,
                expected_runner_id=RUNNER,
                expected_challenge_nonce=NONCE,
                expected_platform=platform,
                expected_host_build_sha256=HOST,
                expected_worker_build_sha256=WORKER, now_unix_ms=NOW)
            self.assertTrue(review.reported_probes_complete)
            self.assertFalse(review.os_isolation_verified)
        receipt = sample_receipt(platform=pb.PLATFORM_LINUX)
        receipt.measurements.add(probe_id="windows-write", observed=pb.EXPECT_DENY,
                                 attempted=True, evidence_sha256=DIGEST)
        with self.assertRaises(ValueError):
            verify(seal(receipt, self.private), self.private,
                   expected_platform=pb.PLATFORM_LINUX)

    def test_unknown_fields_duplicate_tags_and_malformed_envelope_denied(self):
        good = seal(sample_receipt(), self.private)
        for bad in (b"", b"\x00", b"\x0a\xff",
                    good + b"\x98\x06\x01",
                    good + b"\x1a\x07forged!",
                    good + b"x" * 32769,
                    "not-bytes", None):
            with self.subTest(bad=str(bad)[:24]), self.assertRaises(ValueError):
                verify(bad, self.private)

    def test_signature_must_be_pinned_independently_of_envelope(self):
        signer = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        blob = seal(sample_receipt(), self.private)
        for key in (b"", b"invalid", True, None, signer[:-1]):
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(blob, self.private, trusted_public_key=key)

    def test_invalid_time_nonce_and_platform_host_inputs_fail(self):
        blob = seal(sample_receipt(), self.private)
        for args in (
            {"expected_challenge_nonce": "nonce-from-model"},
            {"expected_challenge_nonce": "0" * 64},
            {"expected_host_build_sha256": "0" * 64},
            {"now_unix_ms": True},
            {"expected_platform": pb.PLATFORM_ALL},
            {"expected_platform": True},
            {"expected_runner_id": "with spaces"},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                verify(blob, self.private, **args)

    def test_report_bytes_have_no_grant_or_os_attestation_fields(self):
        field_names = {f.name for f in pb.SupervisorConformanceReceipt.DESCRIPTOR.fields}
        self.assertTrue(field_names.isdisjoint({
            "approved", "authorized", "grant", "credentials", "token",
            "sandbox_verified", "production_enabled", "allow_exec",
        }))

    def test_even_signed_claims_cannot_open_existing_worker_launch_gate(self):
        blob = seal(sample_receipt(), self.private)
        assert verify(blob, self.private).reported_probes_complete
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(
                conformance_report=blob, os_tested=True, key_id=KEY_ID)

    def test_no_private_production_signing_key_is_bundled(self):
        from cognitum import supervisor_conformance
        self.assertFalse(hasattr(supervisor_conformance, "sign_receipt"))
        self.assertFalse(hasattr(supervisor_conformance, "production_private_key"))


if __name__ == "__main__":
    unittest.main()
