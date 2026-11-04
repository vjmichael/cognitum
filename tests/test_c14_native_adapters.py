"""Real optional-library smoke: skip absent dependencies, never substitute mocks.

These require full dependency installation; the user elected to defer final
Lu+transformer task efficacy testing until before Lu 2.0.
"""
import importlib.util
import unittest
from tests.test_c14_closeout import request, invoke

class OptionalNativeSmoke(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('dowhy'), 'DoWhy not installed; native execution NOT_RUN')
    def test_real_dowhy_graph_identification(self):
        r=invoke(request('ate_dowhy'))
        self.assertEqual(r.status,'completed',r.code)
        self.assertTrue(r.has_effect and r.has_interval)
        self.assertAlmostEqual(r.effect,2,delta=.4)

    @unittest.skipUnless(importlib.util.find_spec('econml'), 'EconML not installed; native execution NOT_RUN')
    def test_real_econml_binary_heterogeneous_effect(self):
        r=invoke(request('conditional_effect_econml',n=220))
        self.assertEqual(r.status,'completed',r.code)
        self.assertTrue(r.has_effect and r.has_interval)

    @unittest.skipUnless(importlib.util.find_spec('causallearn'), 'causal-learn not installed; native execution NOT_RUN')
    def test_real_causal_learn_discovery(self):
        r=invoke(request('discover_pc'))
        self.assertEqual(r.status,'completed',r.code)
        self.assertFalse(r.has_effect)
        self.assertEqual(r.estimand,'constraint_based_graph_discovery_not_effect')

    @unittest.skipUnless(importlib.util.find_spec('tigramite'), 'Tigramite not installed; GPL host review NOT_RUN')
    def test_real_pcmci_license_gated_even_when_installed(self):
        # This tests the policy gate, not deployment license approval.
        r=invoke(request('discover_pcmci'))
        self.assertEqual((r.status,r.code),('unavailable','license_review_required'))

if __name__=='__main__':unittest.main()
