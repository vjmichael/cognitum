from dataclasses import replace
from pathlib import Path
import json
import multiprocessing as mp
import tempfile
import time
import unittest
from cognitum.contracts import *
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.policy import authorize
from cognitum.tracing import Trace
from cognitum.evaluation import replay
from cognitum.plugins.calculator import Calculator

class Broken(Calculator):
    def self_test(self): return False

class BadOutput(Calculator):
    def handle(self, operation, payload): return {"value": 5}

class Fault(Calculator):
    def handle(self, operation, payload): raise RuntimeError("SECRET")

class Slow(Calculator):
    def handle(self, operation, payload):
        time.sleep(10)
        return {"value": "1"}

class Writer(Calculator):
    def manifest(self):
        original = super().manifest()
        return replace(original, operations=(replace(original.operations[0], effects=(Effect("write_state", "fixture"),)),))
    def handle(self, operation, payload):
        raise AssertionError("must never be called")

class Research(Calculator):
    def manifest(self): return replace(super().manifest(), track="research")

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        self.runtime = Runtime(self.registry)
        self.context = HostContext("local", "local-user")
        self.request = Request("req", "chain", "calc.rational", {"expression": "1+2"})

    def load(self, factory=Calculator):
        self.registry.install(factory, enabled=True)
        self.registry.nominate("calc", "reference_calc")

    def test_core_only(self):
        self.assertEqual(self.registry.snapshot()["plugins"], [])
        r = self.runtime.call(self.request, self.context)
        self.assertEqual(r.execution_status, "unavailable")
        self.assertIsNone(r.result)
        self.assertTrue(r.limitations)

    def test_explicit_champion_required(self):
        self.registry.install(Calculator, enabled=True)
        self.assertIsNone(self.registry.resolve("calc.rational"))

    def test_default_disabled(self):
        self.registry.install(Calculator)
        self.registry.nominate("calc", "reference_calc")
        self.assertIsNone(self.registry.resolve("calc.rational"))

    def test_live_enable_disable(self):
        self.load()
        self.assertEqual(self.runtime.call(self.request, self.context).result, {"value": "3"})
        self.registry.enable("reference_calc", False)
        self.assertEqual(self.runtime.call(self.request, self.context).execution_status, "unavailable")
        self.registry.enable("reference_calc")
        self.assertEqual(self.runtime.call(self.request, self.context).execution_status, "completed")

    def test_failed_reload_keeps_previous(self):
        self.load()
        before = self.registry.snapshot()
        with self.assertRaises(ValueError): self.registry.install(Broken, enabled=True)
        self.assertEqual(before, self.registry.snapshot())

    def test_successful_reload(self):
        self.load()
        self.registry.install(BadOutput, enabled=True)
        self.assertEqual(self.runtime.call(self.request, self.context).execution_status, "error")
        self.registry.install(Calculator, enabled=True)
        self.assertEqual(self.runtime.call(self.request, self.context).result, {"value": "3"})

    def test_input_validation(self):
        self.load()
        for payload in ({}, {"expression": 1}, {"expression": "1", "grant": True}, {"expression": ""}):
            with self.subTest(payload=payload):
                self.assertEqual(self.runtime.call(replace(self.request, payload=payload), self.context).execution_status, "invalid_input")

    def test_version_rejection(self):
        self.load()
        for request in (replace(self.request, contract_version="2.0.0"), replace(self.request, operation_schema_version="2.0.0")):
            self.assertEqual(self.runtime.call(request, self.context).execution_status, "invalid_input")
        with self.assertRaises(ValueError): replace(Calculator().manifest(), contract_version="1.4.0")

    def test_request_budget_validation(self):
        for timeout in (0, -1, 10001, True, "2"):
            self.assertEqual(self.runtime.call(replace(self.request, timeout_ms=timeout), self.context).execution_status, "invalid_input")

    def test_output_validation(self):
        self.load(BadOutput)
        r = self.runtime.call(self.request, self.context)
        self.assertEqual(r.execution_status, "error")
        self.assertIsNone(r.result)
        self.assertEqual(r.assurance, "unverified")

    def test_fault_sanitized(self):
        self.load(Fault)
        r = self.runtime.call(self.request, self.context)
        self.assertEqual(r.execution_status, "error")
        self.assertNotIn("SECRET", canonical(r.to_dict()))

    def test_timeout_reaps_worker(self):
        self.load(Slow)
        before = {p.pid for p in mp.active_children()}
        r = self.runtime.call(replace(self.request, timeout_ms=200), self.context)
        self.assertEqual(r.execution_status, "timed_out")
        self.assertEqual(before, {p.pid for p in mp.active_children()})

    def test_scope_identity(self):
        self.load()
        r = self.runtime.call(self.request, replace(self.context, workspace_id="other"))
        self.assertEqual(r.error, "identity_scope_mismatch")

    def test_permissions_and_no_effectful_executor(self):
        self.load(Writer)
        self.assertEqual(self.runtime.call(self.request, self.context).error, "permission_denied")
        granted = replace(self.context, grants=frozenset({Effect("write_state", "fixture")}))
        self.assertEqual(self.runtime.call(self.request, granted).error, "effectful_execution_not_implemented")

    def test_read_scope_is_enforced(self):
        op = replace(Calculator().manifest().operations[0], effects=(Effect("read_file", "workspace:a"),))
        wrong = replace(self.context, grants=frozenset({Effect("read_file", "workspace:b")}))
        self.assertEqual(authorize(self.request, wrong, op), "permission_denied")

    def test_replay_denies_effects_even_with_grant(self):
        op = replace(Calculator().manifest().operations[0], effects=(Effect("network", "example.test"),))
        context = replace(self.context, replay=True, grants=frozenset(op.effects))
        self.assertEqual(authorize(self.request, context, op), "replay_requires_inert_deterministic_operation")

    def test_replay_denies_nondeterminism(self):
        op = replace(Calculator().manifest().operations[0], deterministic=False)
        self.assertIsNotNone(authorize(self.request, replace(self.context, replay=True), op))

    def test_research_opt_in(self):
        self.load(Research)
        self.assertIsNone(self.registry.resolve("calc.rational"))
        self.assertIsNotNone(self.registry.resolve("calc.rational", True))

    def test_dry_run_never_executes(self):
        self.load(Fault)
        r = self.runtime.call(replace(self.request, dry_run=True), self.context)
        self.assertEqual(r.execution_status, "validated")
        self.assertIsNone(r.result)

    def test_trace_metadata_only(self):
        self.load()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            runtime = Runtime(self.registry, Trace(path))
            runtime.call(replace(self.request, payload={"expression": "SECRET"}), self.context)
            text = path.read_text()
            self.assertNotIn("SECRET", text)
            event = json.loads(text)
            self.assertEqual(event["correlation_id"], "chain")
            self.assertEqual(event["module"]["version"], "0.1.0")

    def test_assurance_separate_from_interpretation(self):
        self.load()
        r = self.runtime.call(self.request, self.context)
        self.assertEqual(r.assurance, "exact_arithmetic")
        self.assertEqual(r.interpretation["level"], "assumption_bound")

    def test_schema_and_manifest_golden(self):
        golden = json.loads((Path(__file__).parent / "manifest_v1.json").read_text())
        self.assertEqual(Calculator().manifest().describe(), golden)

    def test_smoke_replay_is_repeatable(self):
        self.load()
        cases = [{"id": "one", "operation": "calc.rational", "payload": {"expression": "1/3"},
                  "expected_status": "completed", "expected_result": {"value": "1/3"}}]
        a, b = replay(self.runtime, cases), replay(self.runtime, cases)
        self.assertEqual(a["passed"], 1)
        self.assertEqual(a["suite_hash"], b["suite_hash"])
        self.assertFalse(a["promotion_evidence"])

    def test_fixture_cannot_supply_authority(self):
        with self.assertRaises(ValueError): replay(self.runtime, [{"grants": ["all"]}])

    def test_duplicate_fixture_ids_rejected(self):
        case = {"id": "one", "operation": "missing", "payload": {}, "expected_status": "unavailable", "expected_result": None}
        with self.assertRaises(ValueError): replay(self.runtime, [case, case])

if __name__ == "__main__": unittest.main()
