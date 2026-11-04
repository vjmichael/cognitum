"""Production-facing C14 contracts: actual statsmodels, optional-engine mocks, failure refusal."""
import math
import sys
import types
import unittest
from unittest import mock

from cognitum.proto import causal_pb2 as pb
from cognitum.causal_specialists import run_causal_wire, MAX_INPUT_BYTES

EFFECT=('consistency','no_interference','conditional_exchangeability','positivity')
PC=('causal_markov','faithfulness','causal_sufficiency','iid_sampling')
PCMCI=('causal_markov','faithfulness','causal_sufficiency',
       'causal_stationarity','no_contemporaneous_effects')

def request(op='ate_statsmodels',n=160):
    r=pb.CausalRequest(schema_version=1,operation=op,columns=['T','Y','W','X'],alpha=0.05)
    r.declared_assumptions.extend(EFFECT if op in ('ate_statsmodels','ate_dowhy','conditional_effect_econml') else PC if op=='discover_pc' else PCMCI)
    for i in range(n):
        t=float((i//2)%2)
        w=((i*17)%97)/40.0-1
        x=((i*31)%89)/40.0-1
        y=2.0*t+1.25*w+0.2*x+((i*11)%17-8)*0.04
        r.rows.add(values=[t,y,w,x])
    if op in ('ate_statsmodels','ate_dowhy','conditional_effect_econml'):
        r.treatment='T';r.outcome='Y';r.adjustment.append('W')
    if op=='ate_dowhy':
        for a,b in [('W','T'),('W','Y'),('T','Y')]:r.graph_edges.add(source=a,target=b)
    if op=='conditional_effect_econml':
        r.effect_modifiers.append('X');r.modifier_profile.append(0.25)
    if op=='discover_pcmci':r.max_lag=1
    return r

def invoke(r,**kwargs):
    blob=r.SerializeToString(deterministic=True)
    ans=pb.CausalReply();ans.ParseFromString(run_causal_wire(blob,**kwargs));return ans

class InputTests(unittest.TestCase):
    def test_real_statsmodels_hc3_effect_and_interval(self):
        a=invoke(request())
        self.assertEqual(a.status,'completed');self.assertEqual(a.backend,'statsmodels')
        self.assertTrue(a.has_effect and a.has_interval)
        self.assertAlmostEqual(a.effect,2,delta=0.1)
        self.assertLess(a.interval_lower,a.effect);self.assertGreater(a.interval_upper,a.effect)
        self.assertAlmostEqual(a.confidence_level,.95)
        self.assertEqual(a.uncertainty_kind,'HC3_asymptotic_confidence_interval')
        self.assertIn('assumptions_declared_not_verified',a.limitations)
        self.assertNotIn('global_proof',a.limitations)

    def test_invalid_schema(self):
        q=request();q.schema_version=2
        self.assertEqual(invoke(q).code,'unsupported_operation_or_schema')
    def test_unknown_operation(self):
        q=request();q.operation='__import__'
        self.assertEqual(invoke(q).status,'invalid_input')
    def test_no_assumption_inference(self):
        q=request();q.declared_assumptions.remove('positivity')
        a=invoke(q);self.assertEqual((a.status,a.code),('invalid_input','assumptions_not_declared'))
    def test_reject_malformed_numeric(self):
        q=request();q.rows[0].values[1]=float('nan')
        self.assertEqual(invoke(q).code,'nonfinite_or_ragged_data')
        q=request();q.rows[0].values.pop()
        self.assertEqual(invoke(q).code,'nonfinite_or_ragged_data')
    def test_reject_duplicate_column(self):
        q=request();q.columns[1]='T'
        self.assertEqual(invoke(q).code,'invalid_columns')
    def test_reject_unsafe_identifier(self):
        q=request();q.columns[0]='T;import'
        self.assertEqual(invoke(q).code,'invalid_columns')
    def test_reject_zero_treatment_overlap(self):
        q=request()
        for row in q.rows:row.values[0]=0.0
        self.assertEqual(invoke(q).code,'constant_or_degenerate_column')
    def test_reject_duplicate_adjustment(self):
        q=request();q.adjustment.append('W')
        self.assertEqual(invoke(q).code,'invalid_covariates')
    def test_reject_collinearity(self):
        q=request();q.adjustment.append('X')
        for row in q.rows:row.values[3]=row.values[2]*2
        self.assertEqual(invoke(q).code,'rank_deficient_design')
    def test_reject_invalid_alpha(self):
        q=request();q.alpha=.5
        self.assertEqual(invoke(q).code,'invalid_alpha')
    def test_reject_small_sample(self):
        self.assertEqual(invoke(request(n=20)).code,'invalid_row_count')
    def test_oversize_and_duplicate_noncanonical_wire(self):
        q=request();wire=q.SerializeToString(deterministic=True)
        # Unknown field 101 varint value 1: canonical parser must reject.
        with self.assertRaises(Exception):run_causal_wire(wire + b'\xa8\x06\x01')
        # Duplicate singular schema_version field 1 value 1, not canonical.
        with self.assertRaises(Exception):run_causal_wire(wire+b'\x08\x01')
        with self.assertRaises(Exception):run_causal_wire(b'x'*(MAX_INPUT_BYTES+1))
    def test_request_response_data_hash_not_raw_data(self):
        a=invoke(request());self.assertRegex(a.input_sha256,r'^[0-9a-f]{64}$')
        self.assertNotIn('2.0*t',str(a))
    def test_reject_cyclic_dag(self):
        q=request('ate_dowhy');q.graph_edges.add(source='Y',target='T')
        self.assertEqual(invoke(q).code,'cyclic_graph')
    def test_reject_dag_untrusted_metadata(self):
        q=request('ate_dowhy');q.graph_edges[0].statistic=5.0
        self.assertEqual(invoke(q).code,'invalid_graph_edge')
    def test_no_dag_for_non_dowhy(self):
        q=request();q.graph_edges.add(source='T',target='Y')
        self.assertEqual(invoke(q).code,'unexpected_graph')
    def test_reject_profile_length(self):
        q=request('conditional_effect_econml');q.modifier_profile.pop()
        self.assertEqual(invoke(q).code,'invalid_modifier_profile')
    def test_discovery_refuses_effect_fields(self):
        q=request('discover_pc');q.treatment='T'
        self.assertEqual(invoke(q).code,'unexpected_estimation_fields')
    def test_pcmci_lag_validation(self):
        q=request('discover_pcmci');q.max_lag=0
        self.assertEqual(invoke(q).code,'invalid_lag')
    def test_tigramite_license_fails_closed(self):
        q=request('discover_pcmci')
        a=invoke(q)
        self.assertEqual((a.status,a.code),('unavailable','license_review_required'))
        self.assertFalse(a.has_effect)
    def test_missing_optional_library(self):
        q=request('ate_dowhy')
        a=invoke(q)
        self.assertEqual((a.status,a.code),('unavailable','optional_dependency_unavailable'))
        self.assertFalse(a.has_effect and a.has_interval)
    def test_no_swallow_invalid_wire_as_success(self):
        with self.assertRaises(Exception):run_causal_wire(b'\xff\xff')

class OptionalEngineContractTests(unittest.TestCase):
    def test_dowhy_identification_and_interval(self):
        class Estimand:
            estimands={'backdoor':'foo'}
            def get_backdoor_variables(self):return ['W']
        class Estimate:
            value=2.2
            def get_confidence_intervals(self,confidence_level):
                assert abs(confidence_level-0.95)<1e-9
                return [1.9,2.5]
        class Model:
            def __init__(self,**kwargs):
                self.assertion=kwargs
                assert 'digraph {' in kwargs['graph']
                assert kwargs['proceed_when_unidentifiable'] is False
            def identify_effect(self,**kwargs):return Estimand()
            def estimate_effect(self,*a,**kw):
                assert kw['method_name']=='backdoor.linear_regression'
                assert kw['confidence_intervals']
                return Estimate()
        with mock.patch.dict(sys.modules,{'dowhy':types.SimpleNamespace(CausalModel=Model)}):
            a=invoke(request('ate_dowhy'))
        self.assertEqual(a.status,'completed')
        self.assertAlmostEqual(a.effect,2.2);self.assertTrue(a.has_interval)
    def test_dowhy_refuses_unidentified(self):
        class Model:
            def __init__(self,**kw):pass
            def identify_effect(self,**kw):return None
        with mock.patch.dict(sys.modules,{'dowhy':types.SimpleNamespace(CausalModel=Model)}):
            a=invoke(request('ate_dowhy'))
        self.assertEqual((a.status,a.code),('error','effect_not_identified'))
    def test_dowhy_refuses_missing_interval(self):
        class Estimand:
            estimands={'backdoor':'x'}
            def get_backdoor_variables(self):return ['W']
        class Model:
            def __init__(self,**kw):pass
            def identify_effect(self,**kw):return Estimand()
            def estimate_effect(self,*a,**kw):return types.SimpleNamespace(value=2,get_confidence_intervals=lambda confidence_level:None)
        with mock.patch.dict(sys.modules,{'dowhy':types.SimpleNamespace(CausalModel=Model)}):
            a=invoke(request('ate_dowhy'))
        self.assertEqual((a.status,a.code),('error','interval_not_available'))
    def test_econml_conditional_effect_at_profile(self):
        class LinearDML:
            def __init__(self,**kwargs):assert kwargs['discrete_treatment'];assert kwargs['cv']==3
            def fit(self,**kwargs):self.x=kwargs['X'];assert kwargs['inference']=='auto'
            def effect(self,x,**kw):assert x.shape==(1,1);return [3.0]
            def effect_interval(self,x,**kw):return ([2.0],[4.0])
        with mock.patch.dict(sys.modules,{'econml':types.ModuleType('econml'),
                'econml.dml':types.SimpleNamespace(LinearDML=LinearDML)}):
            a=invoke(request('conditional_effect_econml'))
        self.assertEqual((a.status,a.estimand),('completed','conditional_binary_treatment_effect_at_explicit_profile'))
        self.assertTrue(a.has_interval);self.assertEqual(a.effect,3)
    def test_econml_refuses_nan_ci(self):
        class LinearDML:
            def __init__(self,**kw):pass
            def fit(self,**kw):pass
            def effect(self,*a,**kw):return [2.0]
            def effect_interval(self,*a,**kw):return ([float('nan')],[3.0])
        with mock.patch.dict(sys.modules,{'econml':types.ModuleType('econml'),
                'econml.dml':types.SimpleNamespace(LinearDML=LinearDML)}):
            a=invoke(request('conditional_effect_econml'))
        self.assertEqual((a.status,a.code),('error','malformed_backend_interval'))
        self.assertFalse(a.has_effect)
    def test_pc_distinguishes_orientations_and_no_effect(self):
        import numpy as np
        class Graph:
            graph=np.array([[0,-1,0,0],[1,0,-1,0],[0,-1,0,0],[0,0,0,0]])
        def pc(*a,**kwargs):
            self.assertFalse(kwargs['show_progress'])
            return types.SimpleNamespace(G=Graph())
        fake=types.SimpleNamespace(pc=pc)
        with mock.patch.dict(sys.modules,{'causallearn':types.ModuleType('causallearn'),
                'causallearn.search':types.ModuleType('causallearn.search'),
                'causallearn.search.ConstraintBased':types.ModuleType('causallearn.search.ConstraintBased'),
                'causallearn.search.ConstraintBased.PC':fake}):
            a=invoke(request('discover_pc'))
        self.assertEqual(a.status,'completed');self.assertFalse(a.has_effect)
        self.assertEqual([e.orientation for e in a.discovered_edges],['directed','undirected'])
        self.assertIn('link_statistics_not_treatment_effects',a.limitations)
    def test_pcmci_gpl_gate_and_fdr_p_values(self):
        import numpy as np
        class DataFrame:
            def __init__(self,data,var_names):pass
        class ParCorr:
            def __init__(self,**kw):pass
        class PCMCI:
            def __init__(self,**kw):pass
            def run_pcmci(self,**kw):
                assert kw['fdr_method']=='fdr_bh'
                p=np.ones((4,4,2));v=np.zeros((4,4,2));g=np.full((4,4,2),'',dtype='<U3')
                p[0,1,1]=.01;v[0,1,1]=.35;g[0,1,1]='-->'
                return {'p_matrix':p,'val_matrix':v,'graph':g}
        fake={
          'tigramite':types.ModuleType('tigramite'),
          'tigramite.data_processing':types.SimpleNamespace(DataFrame=DataFrame),
          'tigramite.independence_tests':types.ModuleType('tigramite.independence_tests'),
          'tigramite.independence_tests.parcorr':types.SimpleNamespace(ParCorr=ParCorr),
          'tigramite.pcmci':types.SimpleNamespace(PCMCI=PCMCI)}
        with mock.patch.dict(sys.modules,fake):
            a=invoke(request('discover_pcmci'),enable_gpl_tigramite=True)
        self.assertEqual(a.status,'completed');self.assertFalse(a.has_effect)
        self.assertEqual(len(a.discovered_edges),1)
        self.assertEqual(a.discovered_edges[0].lag,1)
        self.assertEqual(a.uncertainty_kind,'fdr_adjusted_link_p_values_not_confidence_intervals')
    def test_library_exception_sanitized(self):
        class Model:
            def __init__(self,**kw):raise RuntimeError('secret dataset: patient medical info')
        with mock.patch.dict(sys.modules,{'dowhy':types.SimpleNamespace(CausalModel=Model)}):
            a=invoke(request('ate_dowhy'))
        self.assertEqual((a.status,a.code),('error','backend_failure'))
        self.assertNotIn('patient',str(a))

if __name__=='__main__':unittest.main()
