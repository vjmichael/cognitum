"""C14 P2B boundary tests; synthetic checks do not replace a real DoWhy run."""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path
import hashlib
import sys
import unittest

from cognitum.causal_dowhy_backend import (DoWhyWorkerPolicy, worker_source,
    sha256_file, run_dowhy_frame, verify_dowhy_receipt, dowhy_audit, BACKEND_ID,
    SUPPORTED_VERSION, ASSURANCE)
from cognitum.proto import causal_dowhy_pb2 as d, causal_estimation_pb2 as q
from tests.test_c14_estimation import request as estimation_request


def make_request(*, homogenous=False, refutation=False):
    e=estimation_request()
    e.backend=q.DOWHY_OPTIONAL_WORKER
    e.timeout_ms=4500
    if homogenous:
        e.observations.clear()
        for z in (0,1):
            for x,n0,n1 in ((0,16,4),(1,6,14)):
                e.observations.add(states=[z,x,0],count=n0)
                e.observations.add(states=[z,x,1],count=n1)
    return d.DoWhyRequest(schema_version=1,estimation=e,
        method=d.DOWHY_BACKDOOR_LINEAR_REGRESSION,
        refutation=d.DOWHY_PLACEBO_PERMUTATION if refutation else d.DOWHY_REFUTATION_NONE,
        random_seed=42 if refutation else 0,max_expanded_rows=1000)


def go(req, **kwargs):
    raw=req.SerializeToString(deterministic=True)
    reply=run_dowhy_frame(raw,**kwargs)
    return raw,d.DoWhyResult.FromString(reply),reply


def policy(*, enabled=True, attested=True, tampered=False):
    py=Path(sys.executable)
    return DoWhyWorkerPolicy(python_executable=str(py),python_sha256=sha256_file(py),
        worker_sha256=('0'*64 if tampered else sha256_file(worker_source())),
        dispatcher_sha256=sha256_file(Path(worker_source()).with_name('causal_dowhy_backend.py')),
        enabled=enabled,host_isolation_attested=attested)


class C14P2BTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertEqual(go(make_request())[1].status,d.DOWHY_DENIED)

    def test_host_authorization_required(self):
        self.assertEqual(go(make_request(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_host_isolation_required(self):
        self.assertEqual(go(make_request(),enabled=True,host_authorized=True,
                            worker_policy=policy(attested=False))[1].reason_code,'HOST_OS_ISOLATION_NOT_ATTESTED')

    def test_worker_disabled_remains_unavailable(self):
        self.assertEqual(go(make_request(),enabled=True,host_authorized=True,
                            worker_policy=policy(enabled=False))[1].status,d.DOWHY_BACKEND_UNAVAILABLE)

    def test_worker_tampered_rejected_before_spawn(self):
        self.assertEqual(go(make_request(),enabled=True,host_authorized=True,
                            worker_policy=policy(tampered=True))[1].reason_code,'WORKER_INTEGRITY_MISMATCH')

    def test_interpreter_version_not_pinned(self):
        p=policy()
        bad=DoWhyWorkerPolicy(**(dict(p.__dict__) | {'expected_dowhy_version':'unapproved'}))
        self.assertEqual(go(make_request(),enabled=True,host_authorized=True,
                            worker_policy=bad)[1].reason_code,'DOWHY_VERSION_NOT_PINNED')

    def test_subprocess_without_dowhy_produces_no_estimate(self):
        # Executes actual child worker protocol, NOT a real DoWhy 0.14 integration.
        from importlib.util import find_spec
        if find_spec('dowhy') is not None:
            self.skipTest('actual DoWhy installed: separate positive runtime fixture required')
        raw,res,reply=go(make_request(homogenous=True),enabled=True,
                         host_authorized=True,worker_policy=policy())
        self.assertEqual(res.status,d.DOWHY_BACKEND_UNAVAILABLE,(res.reason_code,res))
        self.assertEqual(res.reason_code,'DOWHY_NOT_INSTALLED')
        self.assertFalse(verify_dowhy_receipt(raw,reply).numeric_verified)
        self.assertFalse(res.estimated_ate)

    def test_real_process_timeout_kills_worker(self):
        r=make_request(homogenous=True)
        r.estimation.timeout_ms=1
        raw,res,reply=go(r,enabled=True,host_authorized=True,worker_policy=policy())
        self.assertEqual(res.status,d.DOWHY_TIMEOUT,(res.reason_code,res.status))
        self.assertFalse(verify_dowhy_receipt(raw,reply).numeric_verified)

    def test_actual_dowhy_runtime_when_installed(self):
        # This is the only test eligible to certify real DoWhy API integration.
        from importlib.util import find_spec
        if find_spec('dowhy') is None:
            self.skipTest('DoWhy 0.14 not installed in an OS-isolated pinned environment')
        raw,res,reply=go(make_request(homogenous=True),enabled=True,
                         host_authorized=True,worker_policy=policy())
        self.assertEqual(res.status,d.DOWHY_EFFECT_ESTIMATED,res.reason_code)
        self.assertTrue(verify_dowhy_receipt(raw,reply).numeric_verified)

    def test_not_implemented_frontdoor(self):
        r=make_request();r.method=d.DOWHY_FRONTDOOR_RESERVED
        self.assertEqual(go(r,enabled=True,host_authorized=True)[1].status,d.DOWHY_UNSUPPORTED)

    def test_not_implemented_iv(self):
        r=make_request();r.method=d.DOWHY_INSTRUMENTAL_VARIABLE_RESERVED
        self.assertEqual(go(r,enabled=True,host_authorized=True)[1].status,d.DOWHY_UNSUPPORTED)

    def test_missing_overlap_fail_closed(self):
        r=make_request();del r.estimation.observations[2]
        res=go(r,enabled=True,host_authorized=True,worker_policy=policy())[1]
        self.assertEqual(res.reason_code,'INSUFFICIENT_ARM_OVERLAP')

    def test_failing_backdoor_denied(self):
        r=make_request();r.estimation.identification.adjustment.clear()
        res=go(r,enabled=True,host_authorized=True,worker_policy=policy())[1]
        self.assertEqual(res.reason_code,'BACKDOOR_SUFFICIENCY_NOT_ESTABLISHED')

    def test_sample_expansion_limited(self):
        r=make_request();r.max_expanded_rows=50
        self.assertEqual(go(r)[1].reason_code,'INVALID_DOWHY_REQUEST')

    def test_zero_seed_invalid_for_refutation(self):
        r=make_request(refutation=True);r.random_seed=0
        self.assertEqual(go(r)[1].status,d.DOWHY_DENIED)

    def test_unknown_enum_rejected(self):
        r=make_request();r.method=555
        self.assertEqual(go(r)[1].status,d.DOWHY_DENIED)

    def test_unknown_fields_rejected(self):
        r=make_request()
        raw=r.SerializeToString(deterministic=True)+b'\xc0\x0c\x01'
        res=d.DoWhyResult.FromString(run_dowhy_frame(raw,enabled=True,host_authorized=True))
        self.assertEqual(res.status,d.DOWHY_DENIED)

    def test_forged_result_crosscheck_rejected(self):
        r=make_request(homogenous=True);raw=r.SerializeToString(deterministic=True)
        out=d.DoWhyResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
             trace_id=r.estimation.trace_id,backend_id=BACKEND_ID,backend_version=SUPPORTED_VERSION,
             status=d.DOWHY_EFFECT_ESTIMATED,method=r.method,refutation=r.refutation,
             reason_code='SUPPLIED_GRAPH_NOT_EMPIRICALLY_VERIFIED',graph_criterion_checked=True,
             numeric_crosschecked=True,estimated_ate='500',exact_standardized_reference_ate='1/2',
             absolute_reference_difference='0',total_observations=80,assurance=ASSURANCE)
        reply=out.SerializeToString(deterministic=True)
        self.assertFalse(verify_dowhy_receipt(raw,reply).numeric_verified)

    def test_assumption_forgery_cannot_pass(self):
        r=make_request(homogenous=True);raw=r.SerializeToString(deterministic=True)
        out=d.DoWhyResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
             trace_id=r.estimation.trace_id,backend_id=BACKEND_ID,backend_version=SUPPORTED_VERSION,
             status=d.DOWHY_EFFECT_ESTIMATED,method=r.method,refutation=r.refutation,
             reason_code='REAL_CAUSE_PROVEN',graph_criterion_checked=True,
             numeric_crosschecked=True,estimated_ate='1/2',exact_standardized_reference_ate='1/2',
             absolute_reference_difference='0',total_observations=80,assurance=ASSURANCE)
        self.assertFalse(verify_dowhy_receipt(raw,out.SerializeToString(deterministic=True)).numeric_verified)

    def test_metadata_audit_does_not_serialize_raw_data(self):
        raw,res,reply=go(make_request())
        audit=dowhy_audit(raw,reply)
        self.assertEqual(audit.request_sha256,hashlib.sha256(raw).digest())
        self.assertNotIn(b'synthetic-graph-not-verified',audit.SerializeToString())

    def test_cross_request_replay_detection(self):
        r=make_request(homogenous=True);raw=r.SerializeToString(deterministic=True)
        other=make_request(homogenous=True);other.estimation.observations[0].count+=1
        out=d.DoWhyResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
             trace_id=r.estimation.trace_id,backend_id=BACKEND_ID,backend_version=SUPPORTED_VERSION,
             status=d.DOWHY_EFFECT_ESTIMATED,method=r.method,refutation=r.refutation,
             reason_code='SUPPLIED_GRAPH_NOT_EMPIRICALLY_VERIFIED',graph_criterion_checked=True,
             numeric_crosschecked=True,estimated_ate='1/2',exact_standardized_reference_ate='1/2',
             absolute_reference_difference='0',total_observations=80,assurance=ASSURANCE)
        self.assertFalse(verify_dowhy_receipt(other.SerializeToString(deterministic=True),
                     out.SerializeToString(deterministic=True)).numeric_verified)

if __name__=='__main__':unittest.main()
