"""COG-00: the historical import must share the hardened SSM kernel."""
import unittest
from cognitum.research import ssm_recovered
from cognitum.specialists import ssm

class RecoveredSSMCompatibility(unittest.TestCase):
    def test_single_kernel(self):
        self.assertIs(ssm_recovered.DiagonalSSM, ssm.DiagonalSSM)
        self.assertIs(ssm_recovered.scan_request, ssm.scan_request)
        self.assertIs(ssm_recovered.InvalidSSM, ssm.InvalidSSM)

    def test_restart_above_input_bound(self):
        model = ssm_recovered.DiagonalSSM.from_mapping({
            'a': [0.5], 'b': [[1.0]], 'c': [[1.0]], 'd': [[0.0]]})
        resumed = model.scan([[0.0]], [2000.0])
        self.assertEqual(resumed['final_state'], [1000.0])
