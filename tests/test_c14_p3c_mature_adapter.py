"""C14 P3C verified framing/security paths; real mature-library tests are separate."""
import hashlib
import sys
import unittest
from dataclasses import replace
from cognitum.proto import causal_mature_pb2 as m, causal_heterogeneity_pb2 as h, causal_discovery_pb2 as d
from cognitum.causal_mature_backend import (MatureWorkerPolicy,worker_source,sha256_file,
    run_mature_frame,verify_mature_receipt,mature_audit,_compute_worker,BACKEND_NAMES,ASSURANCE)
from cognitum.causal_heterogeneity import _calculate as reference_heterogeneity
from tests.test_c14_p3_heterogeneity import fixture as hetero_fixture
from tests.test_c14_p3_discovery import fixture as discovery_fixture


def fixtures():
    hetero=hetero_fixture();hetero.method=h.ECONML_CATE_OPTIONAL
    a=m.MatureCausalRequest(schema_version=1,trace_id=hetero.estimation.trace_id,
        backend=m.ECONML_LINEAR_DML_0170,seed=77,timeout_ms=25000,max_expanded_rows=1000)
    a.conditional_effects.CopyFrom(hetero)
    discovery=discovery_fixture();discovery.method=d.CAUSAL_LEARN_PC_OPTIONAL
    discovery.max_tests=250;discovery.max_conditioning=2
    b=m.MatureCausalRequest(schema_version=1,trace_id=discovery.trace_id,
        backend=m.CAUSAL_LEARN_PC_0148,seed=77,timeout_ms=25000,max_expanded_rows=1000)
    b.candidate_graph.CopyFrom(discovery)
    return a,b


def encode(obj):return obj.SerializeToString(deterministic=True)

def policy(backend):
    from cognitum import causal_mature_backend as cb
    return MatureWorkerPolicy(python_executable=sys.executable,
        python_sha256=sha256_file(sys.executable),worker_sha256=sha256_file(worker_source()),
        dispatcher_sha256=sha256_file(cb.__file__),backend=backend,
        pinned_library_version=('0.17.0' if backend==m.ECONML_LINEAR_DML_0170 else '0.1.4.8'),
        enabled=True,host_isolation_attested=True)


class TestC14P3CMatureBoundary(unittest.TestCase):
    def test_default_host_denied(self):
        for req in fixtures():
            with self.subTest(backend=req.backend):
                got=m.MatureCausalResult.FromString(run_mature_frame(encode(req)))
                self.assertEqual(got.status,m.MATURE_REQUEST_DENIED)
                self.assertEqual(got.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_disabled(self):
        for req in fixtures():
            got=m.MatureCausalResult.FromString(run_mature_frame(encode(req),host_authorized=True))
            self.assertEqual(got.reason_code,'MATURE_WORKER_DISABLED')

    def test_host_isolation_denied(self):
        req=fixtures()[0]
        got=m.MatureCausalResult.FromString(run_mature_frame(encode(req),host_authorized=True,enabled=True,
            worker_policy=replace(policy(req.backend),host_isolation_attested=False)))
        self.assertEqual(got.reason_code,'HOST_OS_ISOLATION_NOT_ATTESTED')

    def test_backend_pin_wrong(self):
        req=fixtures()[0]
        got=m.MatureCausalResult.FromString(run_mature_frame(encode(req),host_authorized=True,enabled=True,
            worker_policy=policy(m.CAUSAL_LEARN_PC_0148)))
        self.assertEqual(got.reason_code,'WORKER_BACKEND_PIN_MISMATCH')

    def test_source_tamper_detected(self):
        req=fixtures()[0]
        got=m.MatureCausalResult.FromString(run_mature_frame(encode(req),host_authorized=True,enabled=True,
            worker_policy=replace(policy(req.backend),worker_sha256='0'*64)))
        self.assertEqual(got.reason_code,'WORKER_INTEGRITY_MISMATCH')

    def test_subprocess_protocol_real_child_matches_dependency_availability(self):
        # The same boundary test must work with or without optional libraries.
        # A genuine runtime success is never equivalent to an unavailable backend.
        from importlib.metadata import PackageNotFoundError, version
        from cognitum.causal_mature_backend import BACKEND_PACKAGES
        for req in fixtures():
            with self.subTest(backend=req.backend):
                raw=encode(req)
                reply=run_mature_frame(raw,host_authorized=True,enabled=True,worker_policy=policy(req.backend))
                got=m.MatureCausalResult.FromString(reply)
                package,pin=BACKEND_PACKAGES[req.backend]
                try: installed=version(package)==pin
                except PackageNotFoundError: installed=False
                if installed:
                    self.assertEqual(got.status,m.MATURE_RESULT_CANDIDATE,got.reason_code)
                    self.assertTrue(verify_mature_receipt(raw,reply).request_bound_structure_checked)
                    self.assertFalse(got.causal_assumptions_verified)
                    self.assertFalse(got.orientations_published)
                else:
                    self.assertEqual(got.status,m.MATURE_BACKEND_UNAVAILABLE)
                    self.assertIn(got.reason_code,('LIBRARY_NOT_INSTALLED',
                        'LIBRARY_VERSION_MISMATCH','LIBRARY_DEPENDENCY_UNAVAILABLE'))
                    self.assertFalse(verify_mature_receipt(raw,reply).request_bound_structure_checked)
                self.assertEqual(mature_audit(raw,reply).backend,req.backend)

    def test_wrong_task_rejected(self):
        req=fixtures()[0];req.ClearField('conditional_effects')
        self.assertEqual(m.MatureCausalResult.FromString(run_mature_frame(encode(req))).status,
                         m.MATURE_REQUEST_DENIED)

    def test_wrong_nested_trace(self):
        req=fixtures()[0];req.conditional_effects.estimation.trace_id='other'
        self.assertEqual(m.MatureCausalResult.FromString(run_mature_frame(encode(req))).status,
                         m.MATURE_REQUEST_DENIED)

    def test_expansion_bound(self):
        req=fixtures()[0];req.max_expanded_rows=1
        self.assertEqual(m.MatureCausalResult.FromString(run_mature_frame(encode(req))).status,
                         m.MATURE_REQUEST_DENIED)

    def test_discovery_budget_validation(self):
        req=fixtures()[1];req.candidate_graph.max_tests=2
        self.assertEqual(m.MatureCausalResult.FromString(run_mature_frame(encode(req))).status,
                         m.MATURE_REQUEST_DENIED)

    def test_malformed_wire_rejected(self):
        for data in (b'',b'garbage',b'x'*131073):
            self.assertEqual(m.MatureCausalResult.FromString(run_mature_frame(data)).status,
                             m.MATURE_REQUEST_DENIED)

    def test_forged_candidate_effect(self):
        req=fixtures()[0];raw=encode(req)
        base=req.conditional_effects
        base.method=h.REFERENCE_CONDITIONAL_STANDARDIZATION
        reference=reference_heterogeneity(encode(base))
        out=m.MatureCausalResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
            trace_id=req.trace_id,backend=req.backend,backend_id=BACKEND_NAMES[req.backend],
            runtime_version='0.17.0',status=m.MATURE_RESULT_CANDIDATE,
            reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF',assurance=ASSURANCE,
            sample_count=sum(r.count for r in base.estimation.observations))
        for g in reference.subgroups:
            out.effects.add(modifier_states=g.modifier_states,observations=g.observations,
                estimated_effect=g.estimated_effect,reference_effect=g.estimated_effect,
                absolute_reference_difference='0')
        self.assertTrue(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out.effects[0].estimated_effect='1000'
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out.effects[0].estimated_effect='0';out.effects[0].reference_effect='999'
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out.effects[0].reference_effect=reference.subgroups[0].estimated_effect
        out.request_sha256=b'0'*32
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)

    def test_forged_skeleton(self):
        req=fixtures()[1];raw=encode(req)
        out=m.MatureCausalResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
            trace_id=req.trace_id,backend=req.backend,backend_id=BACKEND_NAMES[req.backend],
            runtime_version='0.1.4.8',status=m.MATURE_RESULT_CANDIDATE,
            reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF',assurance=ASSURANCE,
            sample_count=len(req.candidate_graph.observations))
        out.skeleton_edges.add(first=0,second=1)
        self.assertTrue(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out.orientations_published=True
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)
        out.orientations_published=False
        out.skeleton_edges.add(first=0,second=1)
        self.assertFalse(verify_mature_receipt(raw,encode(out)).request_bound_structure_checked)

    def test_no_causal_proof_receipt(self):
        req=fixtures()[0]; reply=_compute_worker(encode(req))
        self.assertFalse(verify_mature_receipt(encode(req),reply).causal_assumptions_proven)

if __name__=='__main__':unittest.main()
