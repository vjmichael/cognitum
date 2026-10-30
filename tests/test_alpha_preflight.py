"""Alpha preflight has real CLI smoke and negative-certification guarantees."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import alpha_preflight as p

class AlphaPreflightTests(unittest.TestCase):
    def test_real_cli_without_lu(self):
        result = p.probe()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['outcome'], 'PORTABLE_ALPHA_SMOKE_PASS_UNATTESTED')
        for flag in ('lu_integrated', 'release_approved', 'os_worker_isolation_verified', 'independent_evidence_attested'):
            self.assertIs(result[flag], False)

    def test_registry_must_be_empty(self):
        with patch.object(p, '_run', side_effect=[{'passed': True, 'output': {'plugins':['bad'], 'champions':{}}},
                                                    {'passed': True, 'output': {'execution_status':'completed',
                                                            'operation':'calc.rational','result':{'value':'1/2'},
                                                            'assurance':'exact_arithmetic',
                                                            'interpretation':{'level':'assumption_bound'}}}]):
            self.assertFalse(p.probe()['passed'])

    def test_calc_must_return_exact_result(self):
        with patch.object(p, '_run', side_effect=[{'passed': True, 'output': {'plugins':[], 'champions':{}}},
                                                   {'passed': True, 'output': {'execution_status':'completed',
                                                          'operation':'calc.rational', 'result':{'value':'0'},
                                                          'assurance':'exact_arithmetic',
                                                          'interpretation':{'level':'assumption_bound'}}}]):
            self.assertFalse(p.probe()['passed'])

    def test_fail_closed_on_process_timeout(self):
        import subprocess
        with patch.object(p, '_run', side_effect=subprocess.TimeoutExpired('x',1)):
            self.assertEqual(p.probe()['outcome'], 'BLOCKED')

    def test_no_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'evidence.json'
            self.assertEqual(p.main(['--out',str(out)]),0)
            original=out.read_bytes()
            with self.assertRaises(FileExistsError):p.main(['--out',str(out)])
            self.assertEqual(original,out.read_bytes())
            self.assertIs(json.loads(original)['passed'],True)

if __name__ == '__main__':unittest.main()
