"""P50 native subprocess matrix; never promotes worker admission."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from cognitum import alpha_native_fault_probe as probes


@unittest.skipUnless(sys.platform.startswith('linux') and hasattr(probes.os,'pidfd_open'),
                     'Linux pidfd/subreaper required')
class ActualAlphaWorkerFaultTests(unittest.TestCase):
    def test_real_executable_worker_fault_matrix(self):
        evidence = probes.run_fault_matrix()
        self.assertEqual(evidence['status'], 'PASS', evidence)
        self.assertEqual(len(evidence['cases']), 7)
        self.assertEqual(len({x['id'] for x in evidence['cases']}), 7)
        self.assertTrue(all(x['observed'] and x['reaped'] for x in evidence['cases']))
        self.assertTrue(all(x['worker_pid'] > 0 for x in evidence['cases']))
        self.assertEqual(evidence['cases'][0]['detail'], 'typed-reply')
        self.assertEqual(evidence['cases'][-1]['exit_code'], 2)

    def test_exact_worker_source_hash_is_measured(self):
        raw = probes.WORKER.read_bytes()
        self.assertEqual(probes._git_blob(raw), '9c6eb70dcc2f39a77e6f6b9143189e8d727df8b5')
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'f547294522d0b4416bdce76010ca273571ff4820f53f2e2d377ca1fcb1f9c507')

    def test_probe_errors_cannot_be_reported_as_pass(self):
        with patch.object(probes, '_ordinary', side_effect=OSError('injected')):
            evidence = probes.run_fault_matrix(include_crash=False)
        self.assertEqual(evidence['status'], 'FAIL', evidence)
        self.assertTrue(all(c['outcome']=='FAIL' for c in evidence['cases'][:5]))

    def test_valid_typed_output_must_not_claim_lu_or_os_isolation(self):
        wire = probes.make_call('p50','1/3 + 1/6')
        pid, code, accepted, reaped, detail = probes._ordinary(
            probes.struct.pack('>I',len(wire)) + wire, expect=0, validate_reply=True)
        self.assertTrue(pid>0 and code==0 and accepted and reaped, (pid,code,detail))


if __name__ == '__main__': unittest.main()
