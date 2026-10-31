"""Adversarial P47 structural contract tests; synthetic receipts only."""
import copy
import json
import unittest

from cognitum.lifecycle_evidence import (
    REQUIRED_LINUX, InvalidEvidence, evaluate_receipt, MAX_RECEIPT_BYTES,
)


def valid_report():
    return {
        "schema": "cognitum.lifecycle.v1", "platform": "linux",
        "source_sha256": "a" * 64, "runner_id": "synthetic-test",
        "cases": [{"id": name, "outcome": "PASS", "observed": True,
                   "worker_pid": 42, "reaped": True, "live_descendant_pids": []}
                  for name in sorted(REQUIRED_LINUX)],
    }


def assess(doc):
    return evaluate_receipt(json.dumps(doc).encode("utf-8"))


class EvidenceTests(unittest.TestCase):
    def test_complete_fixture_passes_structural_check_only(self):
        result = assess(valid_report())
        self.assertEqual(result["status"], "PASS")
        self.assertIn("NOT OS", result["qualification"])

    def test_missing_probe_fails(self):
        receipt = valid_report(); receipt["cases"].pop()
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_duplicate_and_contradictory_result_fails(self):
        receipt = valid_report(); extra = copy.deepcopy(receipt["cases"][0]); extra["outcome"] = "FAIL"
        receipt["cases"].append(extra)
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_survivor_fails(self):
        receipt = valid_report(); receipt["cases"][0]["live_descendant_pids"] = [99]
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_unreaped_worker_fails(self):
        receipt = valid_report(); receipt["cases"][0]["reaped"] = False
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_unobserved_success_fails(self):
        receipt = valid_report(); receipt["cases"][0]["observed"] = False
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_unknown_case_fails(self):
        receipt = valid_report(); receipt["cases"][0]["id"] = "some-other-case"
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_bool_pid_rejected(self):
        receipt = valid_report(); receipt["cases"][0]["worker_pid"] = True
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_zero_pid_outside_launch_race_fails(self):
        receipt = valid_report(); receipt["cases"][0]["worker_pid"] = 0
        self.assertEqual(assess(receipt)["status"], "FAIL")

    def test_zero_pid_launch_race_allowed(self):
        receipt = valid_report()
        next(c for c in receipt["cases"] if c["id"] == "supervisor-death-launch-race")["worker_pid"] = 0
        self.assertEqual(assess(receipt)["status"], "PASS")

    def test_wrong_source_digest_fails_closed(self):
        data = json.dumps(valid_report()).encode("utf8")
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(data, source_sha256="b" * 64)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(b'{"schema":"one","schema":"two"}')

    def test_nan_rejected(self):
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(b'{"schema":NaN}')

    def test_extremely_long_integer_rejected_as_invalid_evidence(self):
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(b'{"count":' + b'9' * 5000 + b'}')

    def test_extremely_deep_json_rejected_as_invalid_evidence(self):
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(b'[' * 20000 + b']' * 20000)

    def test_oversize_rejected(self):
        with self.assertRaises(InvalidEvidence):
            evaluate_receipt(b"x" * (MAX_RECEIPT_BYTES + 1))

    def test_extra_envelope_field_rejected(self):
        receipt = valid_report(); receipt["approved_for_lu"] = True
        with self.assertRaises(InvalidEvidence):
            assess(receipt)

    def test_empty_runner_rejected(self):
        receipt = valid_report(); receipt["runner_id"] = ""
        with self.assertRaises(InvalidEvidence):
            assess(receipt)

    def test_nonfinite_descendant_type_rejected(self):
        receipt = valid_report(); receipt["cases"][0]["live_descendant_pids"] = [True]
        self.assertEqual(assess(receipt)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
