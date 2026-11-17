"""C13 P2 focused tests; stub pgmpy responses test boundary, not actual pgmpy runtime."""
import hashlib
import unittest
from fractions import Fraction
from pathlib import Path
from types import ModuleType
import sys
from unittest.mock import patch

from cognitum import probability_backend as b
from cognitum.proto import probability_backend_pb2 as q
from tests.test_c13_probability import example


def request(backend=q.REFERENCE_EXACT, query=q.GRAPH_JOINT_POSTERIOR):
    return q.GraphRequest(schema_version=1, inference=example(), backend=backend, query=query)


def execute(req, *, auth=True, enabled=True, policy=None):
    raw = req.SerializeToString(deterministic=True)
    data = b.run_graph_frame(raw, host_authorized=auth, enabled=enabled, worker_policy=policy)
    return raw, data, q.GraphResult.FromString(data)


class TestGraphBackend(unittest.TestCase):
    def test_reference_joint_is_exact(self):
        raw, data, result = execute(request())
        self.assertEqual(result.status, q.GRAPH_SUCCESS)
        self.assertEqual({tuple(cell.states): cell.probability for cell in result.posterior},
                         {(0,): '4/5', (1,): '1/5'})
        self.assertTrue(result.exact_reference_certified)
        receipt = b.verify_graph_receipt(raw, data)
        self.assertTrue(receipt.exact_reference_certified)
        self.assertTrue(b.make_graph_audit(raw, data, receipt).exact_reference_certified)

    def test_reference_map(self):
        raw, data, result = execute(request(query=q.GRAPH_MAP))
        self.assertEqual(tuple(result.map_states), (0,))
        self.assertEqual(result.map_probability, '4/5')
        self.assertFalse(result.posterior)
        self.assertTrue(b.verify_graph_receipt(raw, data).exact_reference_certified)

    def test_conditioned_map(self):
        req = request(query=q.GRAPH_MAP)
        req.inference.hard_evidence.add(node=1, state=1)
        raw, data, result = execute(req)
        self.assertEqual(tuple(result.map_states), (1,))
        self.assertEqual(result.map_probability, '2/3')
        self.assertTrue(b.verify_graph_receipt(raw, data).evidence_valid)

    def test_joint_query_parent_order(self):
        req = request()
        req.inference.targets[:] = [1, 0]
        raw, data, result = execute(req)
        cells = {tuple(c.states): c.probability for c in result.posterior}
        self.assertEqual(cells[(1, 0)], '2/25')
        self.assertEqual(cells[(1, 1)], '4/25')
        self.assertTrue(b.verify_graph_receipt(raw, data).evidence_valid)

    def test_impossible_evidence(self):
        req = request()
        req.inference.model.nodes[1].cpt_ppm[:] = [1000000,0,1000000,0]
        req.inference.hard_evidence.add(node=1, state=1)
        raw, data, result = execute(req)
        self.assertEqual(result.status, q.GRAPH_IMPOSSIBLE_EVIDENCE)
        self.assertTrue(b.verify_graph_receipt(raw, data).evidence_valid)
        self.assertFalse(b.verify_graph_receipt(raw, data).exact_reference_certified)

    def test_tied_map_canonical(self):
        req = request(query=q.GRAPH_MAP)
        req.inference.model.nodes[0].cpt_ppm[:] = [500000, 500000]
        raw, data, result = execute(req)
        self.assertEqual(tuple(result.map_states), (0,))
        self.assertTrue(b.verify_graph_receipt(raw, data).evidence_valid)

    def test_bad_request_and_unknown_backend(self):
        req = request();req.backend = q.GRAPH_BACKEND_UNSPECIFIED
        self.assertEqual(execute(req)[2].status, q.GRAPH_REJECTED)
        req=request();req.tolerance_ppm = 101
        self.assertEqual(execute(req)[2].reason_code, 'INVALID_GRAPH_REQUEST')

    def test_only_exact_inner_query(self):
        req=request();req.inference.method=2;req.inference.samples=100
        self.assertEqual(execute(req)[2].reason_code,'EXACT_GRAPH_QUERY_REQUIRED')

    def test_auth_and_enabled(self):
        self.assertEqual(execute(request(),auth=False)[2].reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertEqual(execute(request(),enabled=False)[2].reason_code,'PROBABILITY_DISABLED')

    def test_budget_unknown_not_impossible(self):
        req=request();req.inference.max_factor_entries=1
        self.assertEqual(execute(req)[2].status,q.GRAPH_UNKNOWN)

    def test_small_verifier_budget_does_not_certify(self):
        req=request();req.inference.max_verifier_assignments=1
        raw,data,result=execute(req)
        self.assertEqual(result.status,q.GRAPH_SUCCESS)
        self.assertFalse(result.independent_numeric_check)
        self.assertFalse(b.verify_graph_receipt(raw,data).evidence_valid)

    def test_forged_posterior_or_map_rejected(self):
        for typ in (q.GRAPH_JOINT_POSTERIOR,q.GRAPH_MAP):
            with self.subTest(typ=typ):
                raw,data,result=execute(request(query=typ))
                if typ == q.GRAPH_MAP: result.map_probability='1'
                else: result.posterior[0].probability='1'
                self.assertFalse(b.verify_graph_receipt(raw,result.SerializeToString()).evidence_valid)

    def test_forged_assurance_flag_rejected(self):
        raw,data,result=execute(request())
        result.exact_reference_certified=False
        self.assertFalse(b.verify_graph_receipt(raw,result.SerializeToString()).evidence_valid)

    def test_forged_backend_version_rejected(self):
        raw,data,result=execute(request())
        result.backend_version=''
        self.assertFalse(b.verify_graph_receipt(raw,result.SerializeToString()).evidence_valid)

    def test_forged_reference_version_rejected(self):
        raw,data,result=execute(request())
        result.backend_version='forged'
        self.assertFalse(b.verify_graph_receipt(raw,result.SerializeToString()).evidence_valid)

    def test_forged_receipt_rejected(self):
        raw,data,_=execute(request())
        receipt=b.verify_graph_receipt(raw,data)
        receipt.enumerated_assignments+=1
        with self.assertRaisesRegex(ValueError,'FORGED_RECEIPT'):
            b.make_graph_audit(raw,data,receipt)

    def test_request_hash_binding(self):
        raw,data,_=execute(request())
        tampered=request();tampered.inference.targets[:] = [1]
        self.assertFalse(b.verify_graph_receipt(tampered.SerializeToString(),data).evidence_valid)

    def test_unavailable_pgmpy_disabled_by_default(self):
        req=request(q.PGMPY_VARIABLE_ELIMINATION)
        raw,data,res=execute(req)
        self.assertEqual(res.status,q.GRAPH_UNKNOWN)
        self.assertEqual(res.reason_code,'PGMPY_WORKER_DISABLED')

    def test_wrong_worker_binary_digest_rejected(self):
        req=request(q.PGMPY_VARIABLE_ELIMINATION)
        policy=b.WorkerPolicy(python_executable=__import__('sys').executable,
                              python_sha256='a'*64,worker_sha256='b'*64,enabled=True)
        self.assertEqual(execute(req,policy=policy)[2].reason_code,'WORKER_INTEGRITY_MISMATCH')

    def test_pgmpy_dependency_unavailable_explicit(self):
        if __import__('importlib').util.find_spec('pgmpy') is not None: self.skipTest('real runtime installed')
        from sys import executable
        policy=b.WorkerPolicy(python_executable=executable,
                              python_sha256=b.sha256_file(Path(executable).resolve()),
                              worker_sha256=b.sha256_file(b.worker_source()),
                              backend_module_sha256=b.sha256_file(Path(b.__file__).resolve()),
                              expected_pgmpy_version='1.1.2',enabled=True)
        self.assertEqual(execute(request(q.PGMPY_VARIABLE_ELIMINATION),policy=policy)[2].reason_code,
                         'PGMPY_NOT_INSTALLED')

    def test_pgmpy_api_mapping_with_stubbed_classes(self):
        """Exercise the real adapter code with fake library classes; NOT a runtime integration test."""
        recorded=[]
        class Graph:
            def __init__(self,edges): self.edges=edges
            def add_nodes_from(self,nodes): self.nodes=nodes
            def add_cpds(self,*cpds): self.cpds=cpds
            def check_model(self): return True
        class CPD:
            def __init__(self,variable,variable_card,values,**kwargs):
                self.variable=variable;self.values=values;self.kwargs=kwargs
                recorded.append(self)
        class Factor:
            variables=['wet','rain']
            values=__import__('numpy').array([[.72,.04],[.08,.16]])
        class Inference:
            def __init__(self,graph): self.graph=graph
            def query(self,**kwargs):
                self.assert_query=kwargs
                return Factor()
        mods={
            'pgmpy': ModuleType('pgmpy'),
            'pgmpy.models': ModuleType('pgmpy.models'),
            'pgmpy.factors': ModuleType('pgmpy.factors'),
            'pgmpy.factors.discrete': ModuleType('pgmpy.factors.discrete'),
            'pgmpy.inference': ModuleType('pgmpy.inference'),
        }
        mods['pgmpy.models'].DiscreteBayesianNetwork=Graph
        mods['pgmpy.factors.discrete'].TabularCPD=CPD
        mods['pgmpy.inference'].VariableElimination=Inference
        mods['pgmpy.inference'].BeliefPropagation=Inference
        req=request(q.PGMPY_VARIABLE_ELIMINATION)
        req.inference.targets[:]=[0,1]
        model=b.base._validate(req.inference)
        with patch.dict(sys.modules,mods),patch.object(b.metadata,'version',return_value='mock-pgmpy'):
            got,version=b._pgmpy_posterior(req,model)
        self.assertEqual(version,'mock-pgmpy')
        self.assertEqual(got,{(0,0):.72,(0,1):.08,(1,0):.04,(1,1):.16})
        self.assertEqual(recorded[0].values,[[.8],[.2]])
        self.assertEqual(recorded[1].values,[[.9,.2],[.1,.8]])
        self.assertEqual(recorded[1].kwargs['evidence'],['rain'])

    def test_fake_pgmpy_return_numerically_verified_not_exact(self):
        """Stubbed adapter contract only: actual third-party backend is not installed."""
        req=request(q.PGMPY_VARIABLE_ELIMINATION)
        raw=req.SerializeToString(deterministic=True)
        with patch.object(b.util, 'find_spec', return_value=object()), patch.object(
            b,'_pgmpy_posterior',return_value=({(0,):0.8,(1,):0.2},'mock-test-version')):
            result_bytes=b._compute(raw,host_authorized=True,enabled=True,in_worker=True)
        result=q.GraphResult.FromString(result_bytes)
        self.assertEqual(result.status,q.GRAPH_SUCCESS)
        self.assertTrue(result.independent_numeric_check)
        self.assertFalse(result.exact_reference_certified)
        receipt=b.verify_graph_receipt(raw,result_bytes)
        self.assertTrue(receipt.numeric_cross_checked)
        self.assertFalse(receipt.exact_reference_certified)

    def test_fake_pgmpy_forged_numeric_result_rejected(self):
        req=request(q.PGMPY_BELIEF_PROPAGATION)
        raw=req.SerializeToString(deterministic=True)
        with patch.object(b.util,'find_spec',return_value=object()), patch.object(
            b,'_pgmpy_posterior',return_value=({(0,):0.9,(1,):0.1},'mock-test-version')):
            result=q.GraphResult.FromString(b._compute(raw,host_authorized=True,enabled=True,in_worker=True))
        self.assertEqual(result.status,q.GRAPH_REJECTED)
        self.assertEqual(result.reason_code,'INDEPENDENT_RESULT_DISAGREEMENT')

    def test_numeric_map_ties_and_error_threshold(self):
        req=request(q.PGMPY_VARIABLE_ELIMINATION,q.GRAPH_MAP)
        raw=req.SerializeToString(deterministic=True)
        with patch.object(b.util,'find_spec',return_value=object()),patch.object(
            b,'_pgmpy_posterior',return_value=({(0,):.8,(1,):.2},'mock-test-version')):
            data=b._compute(raw,host_authorized=True,enabled=True,in_worker=True)
        self.assertTrue(b.verify_graph_receipt(raw,data).numeric_cross_checked)

    def test_no_raw_source_or_executable_from_request(self):
        names={field.name for field in q.GraphRequest.DESCRIPTOR.fields}
        self.assertNotIn('python_executable',names)
        self.assertNotIn('command',names)
        self.assertNotIn('script',names)

    @unittest.skipUnless(__import__('importlib').util.find_spec('pgmpy'), 'pgmpy optional runtime not available')
    def test_real_pgmpy_worker_when_installed(self):
        import sys
        policy=b.WorkerPolicy(python_executable=sys.executable,
                              python_sha256=b.sha256_file(Path(sys.executable).resolve()),
                              worker_sha256=b.sha256_file(b.worker_source()),
                              backend_module_sha256=b.sha256_file(Path(b.__file__).resolve()),
                              expected_pgmpy_version='1.1.2',enabled=True)
        for kind in (q.PGMPY_VARIABLE_ELIMINATION,q.PGMPY_BELIEF_PROPAGATION):
            req=request(kind)
            raw,data,result=execute(req,policy=policy)
            self.assertEqual(result.status,q.GRAPH_SUCCESS,result.reason_code)
            self.assertTrue(b.verify_graph_receipt(raw,data).numeric_cross_checked)
            self.assertFalse(result.exact_reference_certified)

if __name__=='__main__':unittest.main()
