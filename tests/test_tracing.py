"""Trace sink safety tests; no external packages or Lu runtime required."""
import json
from pathlib import Path
import tempfile
import unittest

from cognitum.tracing import Trace, validated_event


def example():
    return {
        "trace_version": "1.0.0", "request_id": "req-1",
        "correlation_id": "cor-1", "operation": "calc.rational",
        "module": {"name": "reference_calc", "version": "0.1.0"},
        "execution_status": "completed", "error": None,
        "latency_ms": 12.25,
    }


class TracingSafetyTests(unittest.TestCase):
    def test_valid_event_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "trace.jsonl"
            sink = Trace(path)
            sink.append(example())
            self.assertEqual(json.loads(path.read_text()), example())
            self.assertEqual(sink.events, [example()])

    def test_unexpected_payload_and_result_are_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as root:
            sink = Trace(Path(root) / "trace.jsonl")
            for key in ("payload", "result", "prompt", "secret", "exception"):
                with self.subTest(key=key):
                    event = example()
                    event[key] = "SECRET"
                    with self.assertRaises(ValueError):
                        sink.append(event)
            self.assertEqual(sink.events, [])
            self.assertFalse((Path(root) / "trace.jsonl").exists())

    def test_nested_module_extra_field_fails_closed(self):
        event = example()
        event["module"]["api_key"] = "SECRET"
        with self.assertRaises(ValueError):
            validated_event(event)

    def test_error_must_be_machine_readable_code(self):
        for bad in ("SECRET: stack trace", "Connection to https://example", "", "secret", 42):
            with self.subTest(error=bad):
                event = example()
                event["error"] = bad
                with self.assertRaises(ValueError):
                    validated_event(event)
        event = example()
        event["error"] = "plugin_timed_out"
        validated_event(event)

    def test_invalid_status_or_missing_fields_rejected(self):
        event = example()
        del event["correlation_id"]
        with self.assertRaises(ValueError):
            validated_event(event)
        event = example()
        event["execution_status"] = "completed SECRET"
        with self.assertRaises(ValueError):
            validated_event(event)

    def test_nonfinite_negative_and_bool_latency_rejected(self):
        for bad in (float("nan"), float("inf"), -1, True, "3"):
            with self.subTest(latency=bad):
                event = example()
                event["latency_ms"] = bad
                with self.assertRaises(ValueError):
                    validated_event(event)

    def test_copy_prevents_caller_mutating_record(self):
        sink = Trace()
        event = example()
        sink.append(event)
        event["module"]["name"] = "changed_after_append"
        self.assertEqual(sink.events[0]["module"]["name"], "reference_calc")

    def test_missing_module_permitted_for_unavailable_capability(self):
        event = example()
        event["module"] = None
        event["execution_status"] = "unavailable"
        self.assertEqual(validated_event(event)["module"], None)

    def test_disk_failure_does_not_record_memory_only_success(self):
        with tempfile.TemporaryDirectory() as root:
            sink = Trace(Path(root) / "missing" / "trace.jsonl")
            with self.assertRaises(OSError):
                sink.append(example())
            self.assertEqual(sink.events, [])


if __name__ == "__main__":
    unittest.main()
