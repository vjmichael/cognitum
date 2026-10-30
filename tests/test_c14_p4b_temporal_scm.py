"""C14 P4B: assumption-bound exact time-sliced causal model."""
import unittest
from cognitum.proto import causal_temporal_scm_pb2 as t
from cognitum.causal_temporal_scm import run_time_scm_frame,time_scm_receipt


def model(op=t.TIME_SCM_OBSERVATIONAL):
    # X_t = X_(t-1) XOR U_t; initial Bernoulli(1/2), innovations Bernoulli(1/2).
    req=t.TimeSCMRequest(schema_version=1,trace_id='c14-p4b',
        assumption_id='discrete-coin-model',steps=3,operation=op,
        target=t.TimedState(variable=0,time=2),max_exogenous_assignments=64,timeout_ms=2500)
    req.variables.add(id='X',states=['zero','one'],initial_probability_ppm=[500000,500000],
        innovation_states=['n0','n1'],innovation_probability_ppm=[500000,500000],
        parents=[t.LaggedParent(variable=0,lag=1)],transition_outputs=[0,1,1,0])
    if op!=t.TIME_SCM_OBSERVATIONAL:req.intervention.CopyFrom(t.TimedState(variable=0,time=0,state=1))
    if op==t.TIME_SCM_COUNTERFACTUAL:
        req.factual_evidence.extend([t.TimedState(variable=0,time=i,state=0) for i in range(3)])
    return req


def feedback():
    # X_t = Y_(t-1), Y_t = X_(t-1), with innovations fixed at 0.
    req=t.TimeSCMRequest(schema_version=1,trace_id='c14-feedback',
        assumption_id='bounded-crosslag-feedback',steps=3,operation=t.TIME_SCM_INTERVENTIONAL,
        target=t.TimedState(variable=1,time=1),
        intervention=t.TimedState(variable=0,time=0,state=1),
        max_exogenous_assignments=128,timeout_ms=2500)
    req.variables.add(id='X',states=['no','yes'],initial_probability_ppm=[500000,500000],
        innovation_states=['n0','n1'],innovation_probability_ppm=[1000000,0],
        parents=[t.LaggedParent(variable=1,lag=1)],transition_outputs=[0,0,1,1])
    req.variables.add(id='Y',states=['no','yes'],initial_probability_ppm=[500000,500000],
        innovation_states=['n0','n1'],innovation_probability_ppm=[1000000,0],
        parents=[t.LaggedParent(variable=0,lag=1)],transition_outputs=[0,0,1,1])
    return req


def evaluate(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=run_time_scm_frame(raw,**kw)
    return raw,t.TimeSCMResult.FromString(reply),reply

class TestP4BTimeSCM(unittest.TestCase):
    def test_observation_is_not_intervention(self):
        raw,got,reply=evaluate(model(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_COMPUTED,got.reason_code)
        self.assertEqual([x.probability for x in got.posterior],['1/2','1/2'])
        self.assertEqual(got.factual_evidence_probability,'1')
        self.assertTrue(got.finite_model_verified)
        self.assertFalse(got.real_world_causation_proven)
        self.assertTrue(time_scm_receipt(raw,reply).exact_model_replay)
    def test_intervention_does_not_imply_counterfactual(self):
        _,got,_=evaluate(model(t.TIME_SCM_INTERVENTIONAL),host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_COMPUTED,got.reason_code)
        self.assertEqual([x.probability for x in got.posterior],['1/2','1/2'])
        self.assertFalse(got.counterfactual_joint)
    def test_factual_abduction_preserves_innovation_world(self):
        raw,got,reply=evaluate(model(t.TIME_SCM_COUNTERFACTUAL),host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_COMPUTED,got.reason_code)
        self.assertEqual(got.factual_evidence_probability,'1/8')
        self.assertEqual([x.probability for x in got.posterior],['0','1'])
        self.assertEqual([x.probability for x in got.counterfactual_joint],['0','1','0','0'])
        self.assertTrue(time_scm_receipt(raw,reply).exact_model_replay)
    def test_time_unrolled_feedback(self):
        raw,got,reply=evaluate(feedback(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_COMPUTED,got.reason_code)
        self.assertEqual([x.probability for x in got.posterior],['0','1'])
        self.assertTrue(time_scm_receipt(raw,reply).exact_model_replay)
    def test_feedback_counterfactual(self):
        req=feedback();req.operation=t.TIME_SCM_COUNTERFACTUAL
        req.factual_evidence.extend([t.TimedState(variable=0,time=0,state=0),
                                     t.TimedState(variable=1,time=1,state=0)])
        _,got,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_COMPUTED,got.reason_code)
        self.assertEqual([x.probability for x in got.posterior],['0','1'])
    def test_impossible_factual_world(self):
        req=feedback();req.operation=t.TIME_SCM_COUNTERFACTUAL
        req.factual_evidence.extend([t.TimedState(variable=0,time=0,state=0),
                                     t.TimedState(variable=1,time=1,state=1)])
        _,got,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(got.status,t.TIME_SCM_IMPOSSIBLE_EVIDENCE,got.reason_code)
        self.assertFalse(got.finite_model_verified)
    def test_denied(self):
        self.assertEqual(evaluate(model(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled(self):
        self.assertEqual(evaluate(model(),host_authorized=True)[1].reason_code,'TIME_SCM_DISABLED')
    def test_invalid_noise_sum(self):
        req=model();req.variables[0].innovation_probability_ppm[0]=100
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_invalid_initial_sum(self):
        req=model();req.variables[0].initial_probability_ppm[0]=100
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_transition_table_wrong_length(self):
        req=model();req.variables[0].transition_outputs.pop()
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_transition_table_invalid_state(self):
        req=model();req.variables[0].transition_outputs[0]=3
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_same_time_cycle_rejected(self):
        req=feedback();req.variables[0].parents[0].lag=0
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'INVALID_LAGGED_GRAPH')
    def test_same_time_parent_from_later_variable_rejected(self):
        req=feedback();req.variables[0].parents.add(variable=1,lag=0)
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_invalid_lag_rejected(self):
        req=model();req.variables[0].parents[0].lag=4
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_exogenous_budget(self):
        req=feedback();req.max_exogenous_assignments=1
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'EXOGENOUS_ENUMERATION_LIMIT')
    def test_duplicate_evidence(self):
        req=model(t.TIME_SCM_COUNTERFACTUAL)
        req.factual_evidence.add(variable=0,time=0,state=0)
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'DUPLICATE_FACTUAL_EVIDENCE')
    def test_intervention_oob(self):
        req=model(t.TIME_SCM_INTERVENTIONAL);req.intervention.time=5
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_missing_counterfactual_evidence(self):
        req=model(t.TIME_SCM_COUNTERFACTUAL);del req.factual_evidence[:]
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_observational_intervention_rejected(self):
        req=model();req.intervention.CopyFrom(t.TimedState(variable=0,time=0,state=1))
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TIME_SCM_REJECTED)
    def test_forged_verified_flag_rejected(self):
        raw,got,_=evaluate(model(),host_authorized=True,enabled=True)
        got.real_world_causation_proven=True
        self.assertFalse(time_scm_receipt(raw,got.SerializeToString(deterministic=True)).exact_model_replay)
    def test_forged_posterior_rejected(self):
        raw,got,_=evaluate(model(),host_authorized=True,enabled=True)
        got.posterior[0].probability='1'
        self.assertFalse(time_scm_receipt(raw,got.SerializeToString(deterministic=True)).exact_model_replay)
    def test_mutated_request_rejected_receipt(self):
        raw,got,reply=evaluate(model(),host_authorized=True,enabled=True)
        req=model();req.timeout_ms+=1
        self.assertFalse(time_scm_receipt(req.SerializeToString(deterministic=True),reply).exact_model_replay)
    def test_oversized_frame(self):
        reply=run_time_scm_frame(b'z'*90001,enabled=True,host_authorized=True)
        self.assertEqual(t.TimeSCMResult.FromString(reply).status,t.TIME_SCM_REJECTED)

if __name__=='__main__':unittest.main()
