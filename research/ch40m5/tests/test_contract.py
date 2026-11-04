"""Static research-acceptance contract tests, not numerical/scientific certification."""
from __future__ import annotations
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FrozenScopeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((ROOT/"CH40M5_ACCEPTANCE_SUMMARY.json").read_text())

    def test_original_fifteen_unique(self):
        cases = self.record["cases"]
        self.assertEqual(len(cases), 15)
        self.assertEqual(len({r["case"] for r in cases}), 15)
        self.assertEqual(sum(r["rows"] == 80 for r in cases), 6)
        self.assertEqual(sum(r["rows"] == 160 for r in cases), 9)

    def test_frozen_data_sha_pins(self):
        for k in ("original_immutable_archive_sha256", "bundled_clp_source_sha256",
                  "strict_original_15_result_sha256", "expanded_original_9_result_sha256",
                  "evidence_zip_sha256"):
            self.assertRegex(self.record[k], r"^[0-9a-f]{64}$")

    def test_real_execution_not_global_certificate(self):
        self.assertEqual(self.record["native_optimizer_executions_successful"], 15)
        self.assertEqual(self.record["independent_feasible_point_checks"], 15)
        self.assertEqual(self.record["certified_global_upper_bounds"], 0)
        self.assertEqual(self.record["closed_scientific_gaps"], 0)
        self.assertTrue(self.record["experiment_no_global_proof"])
        self.assertEqual(self.record["scientific_release"], "NO_GO")

    def test_all_reported_gaps_outside_acceptance(self):
        self.assertEqual(self.record["solver_reported_gap_target"], 0.05)
        self.assertTrue(all(x["reported_gap"] > 0.05 for x in self.record["cases"]))
        self.assertTrue(all(x["independent_point_pass"] for x in self.record["cases"]))
        self.assertTrue(all(x["certified_global_optimum"] is False for x in self.record["cases"]))


if __name__ == "__main__":
    unittest.main()
