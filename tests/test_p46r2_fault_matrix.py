"""P46R2 real Linux negative controls and strict evidence-format checks."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from cognitum import p46r2_fault_matrix as fm


@unittest.skipUnless(sys.platform == 'linux' and hasattr(os, 'pidfd_open'),
                     'Linux process-handle negative fixture')
class ReconstructedP46RemainingFaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = fm.run_fault_matrix()
        cls.guard_sha = hashlib.sha256(fm.GUARD.read_bytes()).hexdigest()
        cls.worker_sha = hashlib.sha256(fm.WORKER.read_bytes()).hexdigest()

    def test_all_fixed_native_cases_have_host_observed_negative_results(self):
        r = self.receipt
        self.assertEqual(r['verdict'], 'NEGATIVE_CONTROLS_OBSERVED', r)
        self.assertEqual([case['id'] for case in r['cases']], list(fm.CASE_IDS))
        self.assertTrue(all(case['expected_observation_matched'] and case['supervisor_sigkill_reaped']
                            and case['pidfd_pinned_before_supervisor_kill']
                            and case['error'] is None for case in r['cases']), r)
        self.assertTrue(all(ch['cleanup_reaped'] and ch['proc_start_ticks'] > 0
                            for case in r['cases'] for ch in case['children'].values()))

    def test_worker_clears_pdeath_and_survives(self):
        result = self.receipt['cases'][0]
        self.assertFalse(result['children']['worker']['exit_observed_after_supervisor_death'])
        self.assertTrue(result['children']['worker']['cleanup_reaped'])

    def test_setsid_descendant_survives_killed_guard(self):
        result = self.receipt['cases'][1]['children']
        self.assertTrue(result['worker']['exit_observed_after_supervisor_death'])
        self.assertFalse(result['descendant']['exit_observed_after_supervisor_death'])
        self.assertTrue(result['descendant']['cleanup_reaped'])

    def test_inherited_writer_keeps_actual_worker_alive(self):
        result = self.receipt['cases'][2]['children']
        self.assertFalse(result['worker']['exit_observed_after_supervisor_death'])
        self.assertFalse(result['writer-holder']['exit_observed_after_supervisor_death'])
        self.assertTrue(all(x['cleanup_reaped'] for x in result.values()))
        self.assertEqual(self.receipt['real_worker_sha256'], self.worker_sha)

    def test_receipt_is_structural_and_never_security_admission(self):
        self.assertEqual(fm.verify_receipt(fm.canonical(self.receipt), self.guard_sha,
                                           self.worker_sha), 'OBSERVED_NEGATIVE_CONTROLS_UNATTESTED')
        self.assertEqual(self.receipt['security_admission'], 'DENIED')
        self.assertFalse(self.receipt['native_containment_verified'])

    def test_false_production_containment_or_authority_is_rejected(self):
        for key, value in (('native_containment_verified', True),
                           ('security_admission', 'AUTHORIZED'),
                           ('assurance', 'OS_KERNEL_SANDBOX_VERIFIED')):
            forged = copy.deepcopy(self.receipt)
            forged[key] = value
            self.assertEqual(fm.verify_receipt(fm.canonical(forged), self.guard_sha,
                                                self.worker_sha), 'INVALID', key)

    def test_malformed_and_duplicate_json_are_rejected(self):
        for bad in (b'', b'[]', b'not json', b'{"schema":1,"schema":2}',
                    b'\xff', b'{' + b'"q":' + b'"A"'*70000 + b'}'):
            self.assertEqual(fm.verify_receipt(bad, self.guard_sha, self.worker_sha), 'INVALID')

    def test_missing_reordered_or_unknown_cases_are_denied(self):
        for corruption in ('delete', 'reorder', 'unknown'):
            forged = copy.deepcopy(self.receipt)
            if corruption == 'delete': forged['cases'].pop()
            elif corruption == 'reorder': forged['cases'].reverse()
            else: forged['cases'][0]['id'] = 'not-a-real-probe'
            self.assertEqual(fm.verify_receipt(fm.canonical(forged), self.guard_sha,
                                                self.worker_sha), 'INVALID')

    def test_source_mismatch_and_missing_cleanup_are_denied(self):
        self.assertEqual(fm.verify_receipt(fm.canonical(self.receipt), '0'*64,
                                           self.worker_sha), 'INVALID')
        forged = copy.deepcopy(self.receipt)
        forged['cases'][0]['children']['worker']['cleanup_reaped'] = False
        self.assertEqual(fm.verify_receipt(fm.canonical(forged), self.guard_sha,
                                           self.worker_sha), 'FAIL')

    def test_forged_survival_cannot_count_as_expected_negative_control(self):
        forged = copy.deepcopy(self.receipt)
        forged['cases'][1]['children']['descendant']['exit_observed_after_supervisor_death'] = True
        self.assertEqual(fm.verify_receipt(fm.canonical(forged), self.guard_sha,
                                           self.worker_sha), 'FAIL')

    def test_unknown_fixture_cannot_spawn_a_process(self):
        with patch.object(fm.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'INVALID_FIXED_CASE'):
                fm._run_one('arbitrary command')
            spawn.assert_not_called()

    def test_real_cgroup2_admission_remains_distinct(self):
        from cognitum import cgroup2_contract as cg
        from cognitum import cgroup2_fixed_runner as runner
        result = cg.preflight()
        if os.statvfs('/sys/fs/cgroup').f_flag & getattr(os, 'ST_RDONLY', 1):
            self.assertEqual(result.reason, 'CGROUP2_READ_ONLY')
            with patch.object(runner.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(cg.ContainmentUnavailable, 'READ_ONLY'):
                    runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00')
                spawn.assert_not_called()
        else:
            self.skipTest('Writable delegated cgroup requires a separately controlled live test')


if __name__ == '__main__':
    unittest.main()
