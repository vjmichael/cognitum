"""C02 acceptance requirements are Protobuf test SPECS, never OS certification."""
import unittest

try:
    from google.protobuf.message import DecodeError
except ModuleNotFoundError:
    raise unittest.SkipTest("optional Cognitum [proto] dependency not installed")

from cognitum.proto import supervisor_acceptance_pb2 as pb
from cognitum.supervisor_acceptance import (
    ACCEPTANCE_TYPE_URL, MAX_PLAN_BYTES, WORKER_WIRE_TYPE,
    OfflineLifecycleCheck, acceptance_plan, encode_acceptance_plan,
    decode_acceptance_plan, check_synthetic_shutdown,
)
from cognitum.worker_wire import start_isolated_worker, admission_status


class SupervisorAcceptanceTests(unittest.TestCase):
    def test_canonical_internal_plan_is_binary_protobuf_not_json(self):
        encoded = encode_acceptance_plan()
        self.assertIsInstance(encoded, bytes)
        self.assertNotEqual(encoded[:1], b"{")
        self.assertLessEqual(len(encoded), MAX_PLAN_BYTES)
        self.assertEqual(decode_acceptance_plan(encoded), acceptance_plan())
        self.assertEqual(pb.DESCRIPTOR.package, "cognitum.security.v1")
        self.assertEqual(
            ACCEPTANCE_TYPE_URL,
            "type.googleapis.com/" + pb.SupervisorAcceptancePlan.DESCRIPTOR.full_name,
        )

    def test_no_runtime_authorization_in_protobuf(self):
        plan = acceptance_plan()
        self.assertFalse(plan.production_launch_enabled)
        self.assertEqual(plan.ce_id, "cognitum.calc")
        self.assertEqual(plan.worker_wire_type, WORKER_WIRE_TYPE)
        self.assertEqual(plan.schema_version, 1)
        forbidden = {"grants", "auth_token", "signature", "permission",
                     "sandbox_verified", "worker_executable", "subject",
                     "enabled", "production_approved", "process_id"}
        self.assertTrue(forbidden.isdisjoint(
            f.name for f in pb.SupervisorAcceptancePlan.DESCRIPTOR.fields))

    def test_all_critical_security_categories_covered(self):
        cases = acceptance_plan().probes
        kinds = {p.kind for p in cases}
        self.assertEqual(kinds, set(range(1, 17)))
        self.assertGreaterEqual(len(cases), 25)
        self.assertEqual(len({p.id for p in cases}), len(cases))
        self.assertTrue(all(0 < len(p.id) <= 64 and len(p.description) <= 200
                            for p in cases))
        self.assertTrue(all(p.expected != pb.EXPECTED_UNSPECIFIED for p in cases))

    def test_restricted_os_cases_exist_for_three_platforms(self):
        probes = acceptance_plan().probes
        for kind in (pb.PRIVATE_FILE_READ, pb.OUT_OF_SCOPE_WRITE,
                     pb.NETWORK_DNS_LOOPBACK, pb.SENSITIVE_HANDLE_INHERITANCE,
                     pb.PROCESS_TREE_BREAKAWAY, pb.RESOURCE_LIMITS):
            with self.subTest(kind=kind):
                covered = {p.platform for p in probes if p.kind == kind}
                self.assertEqual(
                    covered, {pb.PLATFORM_WINDOWS, pb.PLATFORM_LINUX,
                              pb.PLATFORM_MACOS})

    def test_host_lifecycle_probes_are_explicit(self):
        expected = {
            pb.TIMEOUT_AND_CANCEL: pb.EXPECT_KILL_AND_REAP,
            pb.REVOKE_DURING_CALL: pb.EXPECT_KILL_AND_REAP,
            pb.WORKSPACE_CE_UNLOAD: pb.EXPECT_PRESERVE_UNRELATED,
            pb.LATE_REPLY_AFTER_REVOKE: pb.EXPECT_REJECT_LATE_RESULT,
            pb.AUDIT_SECRET_LEAKAGE: pb.EXPECT_METADATA_ONLY,
        }
        probes = {p.kind: p.expected for p in acceptance_plan().probes
                  if p.platform == pb.PLATFORM_ALL}
        for kind, result in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(probes[kind], result)

    def test_plan_tampering_never_confers_launch_permission(self):
        for name, edit in (
            ("enable", lambda p: setattr(p, "production_launch_enabled", True)),
            ("version", lambda p: setattr(p, "schema_version", 2)),
            ("ce", lambda p: setattr(p, "ce_id", "other.ce")),
            ("worker", lambda p: setattr(p, "worker_wire_type", "type.googleapis.com/other")),
            ("drop_scenario", lambda p: p.probes.pop()),
            ("make_pass", lambda p: setattr(p.probes[0], "expected",
                                         pb.EXPECT_RESOURCE_ENFORCEMENT)),
            ("add_grant", lambda p: p.probes.add(id="grant-everything")),
        ):
            with self.subTest(name=name):
                p = pb.SupervisorAcceptancePlan()
                p.CopyFrom(acceptance_plan())
                edit(p)
                with self.assertRaises(ValueError):
                    decode_acceptance_plan(p.SerializeToString(deterministic=True))

    def test_malformed_oversized_and_unknown_proto_fail_closed(self):
        good = encode_acceptance_plan()
        for data in (None, "", b"", b"\x00", b"\x0a\xff",
                     b"x" * (MAX_PLAN_BYTES + 1),
                     good + b"\x98\x06\x01",  # unknown field 99
                     good + b"\x08\x01"):   # duplicate scalar version
            with self.subTest(data=str(data)[:20]), self.assertRaises(ValueError):
                decode_acceptance_plan(data)

    def test_synthetic_revoke_cancel_unload_timeout_sequences(self):
        for trigger in ("cancel_requested", "grant_revoked",
                        "ce_unloaded", "timed_out"):
            events = (
                "synthetic_admission", "synthetic_worker_started", trigger,
                "new_call_denied", "descendant_tree_terminated",
                "descendant_tree_reaped", "late_reply_rejected",
            )
            with self.subTest(trigger=trigger):
                check = check_synthetic_shutdown(events)
                self.assertIsInstance(check, OfflineLifecycleCheck)
                self.assertTrue(check.sequence_valid)
                self.assertFalse(check.os_confinement_verified)
                self.assertFalse(check.launch_permitted)

    def test_synthetic_traces_reject_late_success_and_leaked_descendants(self):
        safe = (
            "synthetic_admission", "synthetic_worker_started",
            "grant_revoked", "new_call_denied",
            "descendant_tree_terminated", "descendant_tree_reaped",
            "late_reply_rejected",
        )
        unsafe = [
            safe[:4] + ("result_accepted",) + safe[5:],
            safe[:5] + ("descendants_still_running",) + safe[6:],
            safe[:3] + ("new_call_allowed",) + safe[4:],
            safe[:4] + ("descendant_tree_reaped", "descendant_tree_terminated") + safe[6:],
            safe[:2] + ("completed",) + safe[3:],
            safe[:-1],
            safe + ("worker_restarted",),
            list(safe),
            ("forged_permission",) + safe[1:],
        ]
        for i, trace in enumerate(unsafe):
            with self.subTest(mutant=i), self.assertRaises(ValueError):
                check_synthetic_shutdown(trace)

    def test_synthetic_event_claims_not_real_os_permission(self):
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(
                sandbox_verified=True, tests_passed=True,
                host="Lu", acceptance=encode_acceptance_plan())

    def test_invalid_probe_enums_rejected_even_if_proto_parses(self):
        cases = [
            (lambda p: setattr(p.probes[0], "platform", pb.PLATFORM_UNSPECIFIED)),
            (lambda p: setattr(p.probes[0], "kind", pb.PROBE_UNSPECIFIED)),
            (lambda p: setattr(p.probes[0], "expected", pb.EXPECTED_UNSPECIFIED)),
        ]
        for change in cases:
            p = acceptance_plan()
            change(p)
            with self.assertRaises(ValueError):
                decode_acceptance_plan(p.SerializeToString(deterministic=True))


if __name__ == "__main__":
    unittest.main()
