"""Offline replay of experimental genuine-library interval report metadata/shape.

This does NOT independently reproduce DoWhy/EconML calculations. Their
scientific executions are recorded separately in the reproducible CLI runner.
"""
import copy
import json
from pathlib import Path
import unittest
from tools import run_c14_p4e_g8_crosslibrary_intervals as cross

PATH=Path(__file__).resolve().parents[1]/'docs/components/causal/P4E-G8-genuine-crosslibrary-intervals.json'

class CrossLibraryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads(PATH.read_text())
    def test_genuine_evidence_shape_replay(self):self.assertTrue(cross.verify_report(self.report))
    def test_no_hidden_confounder_case_is_treated_as_valid_calibration(self):
        self.assertIsNone(self.report['summaries']['hidden_confounder']['do_why_ate_covered_count_descriptive'])
        self.assertTrue(all(not r['dowhy']['coverage_eligible'] for r in self.report['results']
                            if r['oracle']['scenario']=='hidden_confounder'))
    def test_forged_provenance_rejected(self):
        report=copy.deepcopy(self.report);report['source']['dowhy_tag_authenticated']=True
        self.assertFalse(cross.verify_report(report))
    def test_forged_oracle_rejected(self):
        report=copy.deepcopy(self.report);report['results'][0]['oracle']['oracle_ate']=.9
        self.assertFalse(cross.verify_report(report))
    def test_forged_interval_containment_rejected(self):
        report=copy.deepcopy(self.report);report['results'][0]['dowhy']['oracle_covered']=not report['results'][0]['dowhy']['oracle_covered']
        self.assertFalse(cross.verify_report(report))
    def test_cross_request_duplicate_rejected(self):
        report=copy.deepcopy(self.report);report['results'][1]['oracle']=report['results'][0]['oracle']
        self.assertFalse(cross.verify_report(report))

if __name__=='__main__':unittest.main()
