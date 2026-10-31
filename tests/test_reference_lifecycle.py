"""P48: real Linux subprocess lifecycle reference checks, NOT P46 acceptance."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from cognitum.lifecycle_evidence import evaluate_receipt
from cognitum import reference_lifecycle as ref


@unittest.skipUnless(sys.platform.startswith('linux') and Path('/proc').exists(), 'Linux /proc required')
class NativeReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ref._subreaper()

    def test_reference_runner_all_five_os_observed(self):
        result = ref.run_reference_probe()
        self.assertEqual(result['evaluation']['status'], 'PASS', result)
        self.assertEqual(len(result['receipt']['cases']), 5)
        self.assertEqual(result['receipt']['source_sha256'],
                         hashlib.sha256(Path(ref.__file__).read_bytes()).hexdigest())
        self.assertTrue(all(c['observed'] and c['reaped'] for c in result['receipt']['cases']))
        self.assertTrue(result['receipt']['runner_id'].startswith('p48-reference'))

    def test_no_pdeathsig_negative_control_fails(self):
        pid, observed, reaped, survivors = ref._parent_death('idle', disable_pdeath=True)
        self.assertGreater(pid, 0)
        self.assertTrue(observed)
        self.assertFalse(reaped)
        self.assertIn(pid, survivors)
        # Cleanup has killed/reaped the deliberately surviving process.
        self.assertFalse(ref._alive(pid))

    def test_fault_injection_cannot_return_pass(self):
        with patch.object(ref, '_launch_race', side_effect=OSError('injected fault')):
            verdict = ref.run_reference_probe()
        self.assertEqual(verdict['evaluation']['status'], 'FAIL')
        self.assertIn('supervisor-death-launch-race', str(verdict['evaluation']['failures']))

    def test_reference_receipt_wrong_hash_is_invalid(self):
        evidence = ref.run_reference_probe()['receipt']
        wire = json.dumps(evidence).encode('utf-8')
        with self.assertRaisesRegex(ValueError, 'source does not match'):
            evaluate_receipt(wire, source_sha256='0' * 64)


if __name__ == '__main__':
    unittest.main()
