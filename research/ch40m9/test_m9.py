"""CH40-M.9: original-case acceptance metadata and fail-closed negative controls.

These tests do not turn fake inputs into mathematical acceptance: meaningful
acceptance is performed by the real M.8 rational auditor on original cases.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import run_m9 as m

HERE=Path(__file__).resolve().parent
PILOT=HERE/'pilot2'
FULL=HERE/'full15'

class TestM9(unittest.TestCase):
    def test_original_frozen_pinset_is_complete(self):
        if not (m.ROOT/'CH40K/CH40K_ACCEPTANCE.json').is_file():
            self.skipTest('original CH40-K pinned evidence not installed')
        self.assertEqual(len(m.validate_case_list(m.CASE_ORDER)['cases']),15)
    def test_duplicate_case_refused(self):
        with self.assertRaises(m.Refusal):m.validate_case_list([m.CASE_ORDER[0]]*2)
    def test_unknown_case_refused(self):
        with self.assertRaises(m.Refusal):m.validate_case_list(['made_up_source'])
    def test_missing_metrics_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'time.txt';f.write_text('user=0.5\nsystem=0.2\n')
            with self.assertRaises(m.Refusal):m.read_time(f)
    def test_negative_time_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'time.txt'
            f.write_text('user=-1\nsystem=0\nrss_kib=100\nelapsed_seconds=2\nexit_status=0\n')
            with self.assertRaises(m.Refusal):m.read_time(f)
    def test_atomic_output_writes_complete_json(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'report.json'
            m.atomic_json(f,{'hello':['world']})
            self.assertEqual(json.loads(f.read_text()),{'hello':['world']})
            self.assertFalse(f.with_suffix('.json.tmp').exists())
    def get_reports(self):
        if not (PILOT/'CH40M9_ACCEPTANCE.json').exists():
            self.skipTest('original 2-case evidence unavailable')
        return (json.loads((PILOT/'cache_audit.json').read_text()),
                json.loads((PILOT/'fresh_audit.json').read_text()))
    def test_original_pilot_journals_accepted(self):
        cache,fresh=self.get_reports()
        self.assertTrue(m.compare_audits(cache,fresh,PILOT/'journals',[m.CASE_ORDER[0],m.CASE_ORDER[4]]))
    def test_rehashed_journal_bytes_refused(self):
        cache,fresh=self.get_reports()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            for f in (PILOT/'journals').glob('*.json'):
                (target/f.name).write_bytes(f.read_bytes())
            filename=cache['receipts'][0]['journal_file']
            f=target/filename
            # Valid JSON, byte identity differs: external receipt must now fail.
            f.write_text(f.read_text()+'\n')
            with self.assertRaises(m.Refusal):m.compare_audits(cache,fresh,target,[m.CASE_ORDER[0],m.CASE_ORDER[4]])
    def test_modified_receipt_refused(self):
        cache,fresh=self.get_reports()
        fresh['receipts'][0]['final_upper']='-999'
        with self.assertRaises(m.Refusal):m.compare_audits(cache,fresh,PILOT/'journals',[m.CASE_ORDER[0],m.CASE_ORDER[4]])
    def test_modified_proof_ledger_refused(self):
        cache,fresh=self.get_reports()
        cache['propositions'][0]['independent_upper']='0'
        with self.assertRaises(m.Refusal):m.compare_audits(cache,fresh,PILOT/'journals',[m.CASE_ORDER[0],m.CASE_ORDER[4]])
    def test_false_release_refused(self):
        cache,fresh=self.get_reports()
        cache['scientific_release']='PASS'
        with self.assertRaises(m.Refusal):m.compare_audits(cache,fresh,PILOT/'journals',[m.CASE_ORDER[0],m.CASE_ORDER[4]])
    def test_missing_original_case_audit_refused(self):
        cache,fresh=self.get_reports()
        cache['receipts'].pop()
        with self.assertRaises(m.Refusal):m.compare_audits(cache,fresh,PILOT/'journals',[m.CASE_ORDER[0],m.CASE_ORDER[4]])
    def test_full15_acceptance_when_present(self):
        final=FULL/'CH40M9_ACCEPTANCE.json'
        if not final.exists():self.skipTest('15-case current-run result not yet available')
        d=json.loads(final.read_text())
        cache=json.loads((FULL/'cache_audit.json').read_text())
        fresh=json.loads((FULL/'fresh_audit.json').read_text())
        self.assertTrue(m.compare_audits(cache,fresh,FULL/'journals',m.CASE_ORDER))
        self.assertEqual(d['original_cases'],15)
        self.assertEqual(d['paired_worker_runs'],30)
        self.assertEqual(d['online_rational_checks'],cache['children_checked'])
        self.assertEqual(d['scientific_release'],'NO_GO')

if __name__=='__main__':unittest.main()
