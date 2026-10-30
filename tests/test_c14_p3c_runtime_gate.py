"""Positive integration tests only pass when *real pinned libraries* are installed.

These cannot be substituted by a fake module or a mock worker. All worker
execution here uses a development-only policy and is NOT Lu OS attestation.
"""
from importlib.metadata import PackageNotFoundError,version
import unittest
from tests.test_c14_p3c_mature_adapter import fixtures,policy,encode
from cognitum.causal_mature_backend import run_mature_frame,verify_mature_receipt
from cognitum.proto import causal_mature_pb2 as m


def available(name,pin):
    try:return version(name)==pin
    except PackageNotFoundError:return False

class TestP3CRealDependencyGate(unittest.TestCase):
    @unittest.skipUnless(available('econml','0.17.0'),'REAL_ECONML_0_17_0_NOT_INSTALLED')
    def test_real_econml_linear_dml(self):
        req=fixtures()[0];raw=encode(req)
        got=m.MatureCausalResult.FromString(run_mature_frame(raw,host_authorized=True,
            enabled=True,worker_policy=policy(req.backend)))
        self.assertEqual(got.status,m.MATURE_RESULT_CANDIDATE,got.reason_code)
        self.assertTrue(verify_mature_receipt(raw,encode(got)).request_bound_structure_checked)
        self.assertGreater(len(got.effects),0)
        self.assertFalse(got.causal_assumptions_verified)

    @unittest.skipUnless(available('causal-learn','0.1.4.8'),'REAL_CAUSAL_LEARN_0_1_4_8_NOT_INSTALLED')
    def test_real_causal_learn_pc(self):
        req=fixtures()[1];raw=encode(req)
        got=m.MatureCausalResult.FromString(run_mature_frame(raw,host_authorized=True,
            enabled=True,worker_policy=policy(req.backend)))
        self.assertEqual(got.status,m.MATURE_RESULT_CANDIDATE,got.reason_code)
        self.assertTrue(verify_mature_receipt(raw,encode(got)).request_bound_structure_checked)
        self.assertFalse(got.orientations_published)
        self.assertFalse(got.causal_assumptions_verified)

if __name__=='__main__':unittest.main()
