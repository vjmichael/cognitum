"""G5 genuine optional scientific backends (not fake or mocked scientific results).

This test harness explicitly models a development authorization/isolation grant.
It does NOT prove Lu authentication or native Windows process containment.
"""
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
import hashlib
import math
import unittest

from cognitum.causal_mature_backend import (
    BACKEND_PACKAGES, run_mature_frame, verify_mature_receipt,
)
from cognitum.proto import causal_mature_pb2 as m
from tests.test_c14_p3c_mature_adapter import fixtures, encode, policy


def available(backend):
    pkg,pin=BACKEND_PACKAGES[backend]
    try: return version(pkg)==pin
    except PackageNotFoundError: return False


class TestG5GenuineMatureWorkers(unittest.TestCase):
    def _run(self,req,**kwargs):
        raw=encode(req)
        pol=kwargs.pop('worker_policy',policy(req.backend))
        reply=run_mature_frame(raw,host_authorized=True,enabled=True,
                               worker_policy=pol,**kwargs)
        return raw,reply,m.MatureCausalResult.FromString(reply)

    @unittest.skipUnless(available(m.ECONML_LINEAR_DML_0170),'EconML 0.17.0 not installed')
    def test_econml_real_subprocess_and_replay(self):
        req=fixtures()[0]
        raw,reply,out=self._run(req)
        self.assertEqual(out.status,m.MATURE_RESULT_CANDIDATE,out.reason_code)
        self.assertEqual(out.runtime_version,'0.17.0')
        self.assertEqual(out.sample_count,100)
        self.assertGreater(len(out.effects),0)
        self.assertTrue(verify_mature_receipt(raw,reply).request_bound_structure_checked)
        self.assertFalse(out.causal_assumptions_verified)
        for entry in out.effects:
            self.assertTrue(math.isfinite(float(entry.estimated_effect)))
            self.assertTrue(math.isfinite(float(entry.absolute_reference_difference)))
        _,second_reply,second=self._run(req)
        self.assertEqual([x.estimated_effect for x in out.effects],
                         [x.estimated_effect for x in second.effects])
        self.assertTrue(verify_mature_receipt(raw,second_reply).request_bound_structure_checked)

    @unittest.skipUnless(available(m.CAUSAL_LEARN_PC_0148),'causal-learn 0.1.4.8 not installed')
    def test_causal_learn_real_subprocess_and_replay(self):
        req=fixtures()[1]
        raw,reply,out=self._run(req)
        self.assertEqual(out.status,m.MATURE_RESULT_CANDIDATE,out.reason_code)
        self.assertEqual(out.runtime_version,'0.1.4.8')
        self.assertEqual(out.sample_count,250)
        self.assertEqual([(e.first,e.second) for e in out.skeleton_edges],[(0,1),(1,2)])
        self.assertTrue(verify_mature_receipt(raw,reply).request_bound_structure_checked)
        self.assertFalse(out.orientations_published)
        self.assertFalse(out.causal_assumptions_verified)
        _,second_reply,second=self._run(req)
        self.assertEqual(encode(out.skeleton_edges[0]),encode(second.skeleton_edges[0]))
        self.assertTrue(verify_mature_receipt(raw,second_reply).request_bound_structure_checked)

    def test_requires_auth_and_host_isolation(self):
        for req in fixtures():
            with self.subTest(backend=req.backend):
                raw=encode(req)
                denied=m.MatureCausalResult.FromString(run_mature_frame(raw,enabled=True,
                    worker_policy=policy(req.backend)))
                self.assertEqual(denied.reason_code,'HOST_AUTHORIZATION_REQUIRED')
                denied=m.MatureCausalResult.FromString(run_mature_frame(raw,
                    host_authorized=True,enabled=True,
                    worker_policy=replace(policy(req.backend),host_isolation_attested=False)))
                self.assertEqual(denied.reason_code,'HOST_OS_ISOLATION_NOT_ATTESTED')

    def test_source_tamper_denied(self):
        for req in fixtures():
            with self.subTest(backend=req.backend):
                _,_,out=self._run(req,worker_policy=replace(policy(req.backend),
                    dispatcher_sha256='0'*64))
                self.assertEqual(out.reason_code,'WORKER_INTEGRITY_MISMATCH')

    def test_pin_mismatch_denied(self):
        for req in fixtures():
            with self.subTest(backend=req.backend):
                _,_,out=self._run(req,worker_policy=replace(policy(req.backend),
                    pinned_library_version='wrong'))
                self.assertEqual(out.reason_code,'WORKER_BACKEND_PIN_MISMATCH')

    @unittest.skipUnless(available(m.ECONML_LINEAR_DML_0170),'EconML 0.17.0 not installed')
    def test_forged_econml_receipt_rejected(self):
        raw,reply,out=self._run(fixtures()[0])
        self.assertTrue(verify_mature_receipt(raw,reply).request_bound_structure_checked)
        out.effects[0].reference_effect='123456'
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out=m.MatureCausalResult.FromString(reply)
        out.causal_assumptions_verified=True
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)

    @unittest.skipUnless(available(m.CAUSAL_LEARN_PC_0148),'causal-learn 0.1.4.8 not installed')
    def test_forged_causal_learn_orientation_rejected(self):
        raw,reply,out=self._run(fixtures()[1])
        self.assertTrue(verify_mature_receipt(raw,reply).request_bound_structure_checked)
        out.orientations_published=True
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out=m.MatureCausalResult.FromString(reply)
        out.request_sha256=hashlib.sha256(b'different').digest()
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)

if __name__ == '__main__': unittest.main()
