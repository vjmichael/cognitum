"""Positive DoWhy 0.14 runtime gates. Skips are NOT passes or deployment approval.

These only test a local isolated subprocess candidate. Authenticated Windows Job Object
confinement, offline signed lock provenance, and Lu host admission need separate gates.
"""
import importlib.metadata
import unittest

from cognitum.causal_dowhy_backend import verify_dowhy_receipt
from cognitum.proto import causal_dowhy_pb2 as d
from tests.test_c14_dowhy_adapter import make_request, go, policy


class RealDoWhyRuntimeGate(unittest.TestCase):
    def setUp(self):
        try:
            installed=importlib.metadata.version('dowhy')
        except importlib.metadata.PackageNotFoundError:
            self.skipTest('Real DoWhy runtime unavailable: positive integration NOT verified')
        self.assertEqual(installed,'0.14', 'Unreviewed DoWhy runtime version')

    def test_real_backdoor_estimation(self):
        raw,result,reply=go(make_request(homogenous=True),enabled=True,
                            host_authorized=True,worker_policy=policy())
        self.assertEqual(result.status,d.DOWHY_EFFECT_ESTIMATED,result.reason_code)
        self.assertTrue(verify_dowhy_receipt(raw,reply).numeric_verified)

    def test_real_placebo_diagnostic(self):
        raw,result,reply=go(make_request(homogenous=True,refutation=True),enabled=True,
                            host_authorized=True,worker_policy=policy())
        self.assertEqual(result.status,d.DOWHY_EFFECT_ESTIMATED,result.reason_code)
        self.assertTrue(result.refutation_executed)
        self.assertEqual(result.refutation_reason_code,'PLACEBO_DIAGNOSTIC_ONLY')
        self.assertTrue(verify_dowhy_receipt(raw,reply).numeric_verified)


if __name__ == '__main__':
    unittest.main()
