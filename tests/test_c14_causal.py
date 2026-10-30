"""C14 P1 functional and adversarial tests, not statistical benchmarks."""
from __future__ import annotations
import hashlib
import itertools
import random
import unittest
from fractions import Fraction
from cognitum.causal import run_causal_frame,verify_causal_result,causal_receipt,causal_audit,_parse,_execute,_backdoor
from cognitum.proto import causal_pb2 as p


def model():
    """U -> X, U -> Y, X -> Y with Y = X xor U; hidden confounding."""
    return p.StructuralCausalModel(
        assumption_id='user-supplied-scm-v1',
        exogenous=[p.ExogenousVariable(id='U',states=['u0','u1'],probability_ppm=[500000,500000])],
        endogenous=[
            p.EndogenousVariable(id='X',states=['no','yes'],noise=[0],function_outputs=[0,1]),
            p.EndogenousVariable(id='Y',states=['no','yes'],parents=[0],noise=[0],function_outputs=[0,1,1,0]),
        ])


def request(op=p.OBSERVATIONAL_QUERY, **kw):
    return p.CausalRequest(schema_version=1,trace_id='trace-C14',operation=op,
                           model=model(),target=1,max_exogenous_assignments=128,timeout_ms=1000,**kw)


def go(req, authorized=True, enabled=True):
    frame=req.SerializeToString(deterministic=True)
    result=p.CausalResult.FromString(run_causal_frame(frame,host_authorized=authorized,enabled=enabled))
    return frame,result

class C14Tests(unittest.TestCase):
    def test_observation_not_intervention(self):
        f,r=go(request())
        self.assertEqual(r.status,p.EXACT_MODEL_RESULT)
        self.assertEqual([v.probability for v in r.posterior],['1','0'])
        self.assertEqual(r.factual_evidence_probability,'1')
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_intervention_breaks_structural_equation_not_noise(self):
        q=request(p.INTERVENTIONAL_QUERY,interventions=[p.StateObservation(variable=0,state=1)])
        f,r=go(q)
        self.assertEqual([v.probability for v in r.posterior],['1/2','1/2'])
        self.assertEqual(r.status,p.EXACT_MODEL_RESULT)
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_abduction_action_prediction_shared_latent_state(self):
        q=request(p.COUNTERFACTUAL_QUERY,
                  factual_evidence=[p.StateObservation(variable=0,state=0)],
                  interventions=[p.StateObservation(variable=0,state=1)])
        f,r=go(q)
        self.assertEqual(r.factual_evidence_probability,'1/2')
        self.assertEqual([v.probability for v in r.posterior],['0','1'])
        self.assertEqual([v.probability for v in r.joint],['0','1','0','0'])
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_factual_evidence_beyond_latent_support(self):
        q=request(p.COUNTERFACTUAL_QUERY,
                  factual_evidence=[p.StateObservation(variable=0,state=1),p.StateObservation(variable=1,state=1)],
                  interventions=[p.StateObservation(variable=0,state=0)])
        f,r=go(q)
        self.assertEqual(r.status,p.IMPOSSIBLE_FACTUAL_EVIDENCE)
        self.assertFalse(causal_receipt(f,r.SerializeToString(deterministic=True)).evidence_valid)
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_counterfactual_without_evidence_rejected(self):
        _,r=go(request(p.COUNTERFACTUAL_QUERY,interventions=[p.StateObservation(variable=0,state=1)]))
        self.assertEqual(r.status,p.REJECTED_CAUSAL)

    def test_intervention_with_factual_evidence_rejected(self):
        _,r=go(request(p.INTERVENTIONAL_QUERY,
             interventions=[p.StateObservation(variable=0,state=1)],
             factual_evidence=[p.StateObservation(variable=1,state=0)]))
        self.assertEqual(r.status,p.REJECTED_CAUSAL)

    def test_confounded_backdoor_no_adjustment(self):
        f,r=go(request(p.BACKDOOR_CHECK,treatment=0))
        self.assertEqual(r.status,p.BACKDOOR_NOT_CERTIFIED)
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_negative_backdoor_receipt_is_not_identification(self):
        f,r=go(request(p.BACKDOOR_CHECK,treatment=0))
        self.assertEqual(r.status,p.BACKDOOR_NOT_CERTIFIED)
        self.assertTrue(r.independently_checked)
        self.assertFalse(causal_receipt(f,r.SerializeToString(deterministic=True)).evidence_valid)

    def test_adjustment_for_descendant_is_forbidden(self):
        q=request(p.BACKDOOR_CHECK,treatment=0)
        q.model.endogenous.add(id='D',states=['a','b'],parents=[0],function_outputs=[0,1])
        q.adjustment.append(2)
        self.assertEqual(go(q)[1].status,p.BACKDOOR_NOT_CERTIFIED)

    def test_valid_backdoor_with_observed_common_cause(self):
        q=request(p.BACKDOOR_CHECK,treatment=1)
        # construct graph U -> Z -> X and U -> Z -> Y, with X -> Y
        # adjustment on Z makes the backdoor path through Z blocked.
        q.model.endogenous.clear()
        q.model.endogenous.extend([
            p.EndogenousVariable(id='Z',states=['no','yes'],noise=[0],function_outputs=[0,1]),
            p.EndogenousVariable(id='X',states=['no','yes'],parents=[0],function_outputs=[0,1]),
            p.EndogenousVariable(id='Y',states=['no','yes'],parents=[0,1],function_outputs=[0,1,1,1]),
        ])
        q.target=2
        self.assertEqual(go(q)[1].status,p.BACKDOOR_NOT_CERTIFIED)
        q.adjustment.append(0)
        f,r=go(q)
        self.assertEqual(r.status,p.BACKDOOR_CERTIFIED)
        self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_adjusting_for_collider_not_a_backdoor(self):
        q=request(p.BACKDOOR_CHECK,treatment=0)
        q.model.exogenous.clear()
        q.model.exogenous.extend([
            p.ExogenousVariable(id='U',states=['a','b'],probability_ppm=[500000,500000]),
            p.ExogenousVariable(id='V',states=['a','b'],probability_ppm=[500000,500000]),
        ])
        q.model.endogenous.clear()
        q.model.endogenous.extend([
            p.EndogenousVariable(id='X',states=['a','b'],noise=[0],function_outputs=[0,1]),
            p.EndogenousVariable(id='Y',states=['a','b'],noise=[1],function_outputs=[0,1]),
            p.EndogenousVariable(id='C',states=['a','b'],parents=[0,1],function_outputs=[0,1,1,1]),
        ])
        self.assertEqual(go(q)[1].status,p.BACKDOOR_CERTIFIED)
        q.adjustment.append(2)
        self.assertEqual(go(q)[1].status,p.BACKDOOR_NOT_CERTIFIED)

    def test_reject_adjust_descendant(self):
        q=request(p.BACKDOOR_CHECK,treatment=0,adjustment=[1])
        self.assertEqual(go(q)[1].status,p.REJECTED_CAUSAL) # outcome cannot adjust

    def test_reject_structural_cycle(self):
        q=request();q.model.endogenous[0].parents.append(1)
        q.model.endogenous[0].function_outputs.extend([0,1])
        self.assertEqual(go(q)[1].status,p.REJECTED_CAUSAL)

    def test_reject_structural_table_mismatch(self):
        q=request();q.model.endogenous[1].function_outputs.pop()
        self.assertEqual(go(q)[1].status,p.REJECTED_CAUSAL)

    def test_reject_invalid_noise_distribution(self):
        q=request();q.model.exogenous[0].probability_ppm[0]=400000
        self.assertEqual(go(q)[1].status,p.REJECTED_CAUSAL)

    def test_duplicate_evidence_denied(self):
        q=request(factual_evidence=[p.StateObservation(variable=0,state=0)]*2)
        self.assertEqual(go(q)[1].status,p.REJECTED_CAUSAL)

    def test_unknown_resource_limit_never_certified(self):
        q=request();q.max_exogenous_assignments=1
        f,r=go(q)
        self.assertEqual(r.status,p.INCONCLUSIVE_CAUSAL)
        self.assertFalse(r.independently_checked)
        self.assertFalse(causal_receipt(f,r.SerializeToString(deterministic=True)).evidence_valid)

    def test_host_authorization_denied(self):
        f,r=go(request(),authorized=False)
        self.assertEqual(r.status,p.REJECTED_CAUSAL)
        self.assertFalse(r.independently_checked)
        self.assertFalse(causal_receipt(f,r.SerializeToString(deterministic=True)).evidence_valid)

    def test_disabled_by_default(self):
        self.assertEqual(go(request(),enabled=False)[1].status,p.REJECTED_CAUSAL)

    def test_receipt_hashes_match_and_audit_minimized(self):
        f,r=go(request())
        out=r.SerializeToString(deterministic=True)
        rec=causal_receipt(f,out);a=causal_audit(f,out)
        self.assertTrue(rec.evidence_valid)
        self.assertEqual(rec.request_sha256,hashlib.sha256(f).digest())
        self.assertEqual(rec.result_sha256,hashlib.sha256(out).digest())
        self.assertEqual(a.result_sha256,rec.result_sha256)
        self.assertNotIn(b'user-supplied-scm',a.SerializeToString())

    def test_forged_posterior_rejected(self):
        f,r=go(request())
        r.posterior[0].probability='0'
        self.assertFalse(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_forged_counterfactual_joint_rejected(self):
        q=request(p.COUNTERFACTUAL_QUERY,factual_evidence=[p.StateObservation(variable=0,state=0)],
                  interventions=[p.StateObservation(variable=0,state=1)])
        f,r=go(q)
        r.joint[0].probability='1'
        self.assertFalse(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_forged_assurance_rejected(self):
        f,r=go(request());r.assurance='IDENTIFIED_FROM_DATA'
        self.assertFalse(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_cross_request_replay_denied(self):
        f,r=go(request());different=request();different.model.assumption_id='changed-model'
        self.assertFalse(verify_causal_result(different.SerializeToString(deterministic=True),r.SerializeToString(deterministic=True)))

    def test_forged_status_rejected(self):
        f,r=go(request());r.status=p.BACKDOOR_CERTIFIED
        self.assertFalse(verify_causal_result(f,r.SerializeToString(deterministic=True)))

    def test_check_independent_model_random_counterfactuals(self):
        rand=random.Random(1401)
        for _ in range(60):
            q=request(p.COUNTERFACTUAL_QUERY,
                factual_evidence=[p.StateObservation(variable=0,state=rand.randrange(2))],
                interventions=[p.StateObservation(variable=0,state=rand.randrange(2))])
            out=q.model.endogenous[1].function_outputs
            out[:]=[rand.randrange(2) for _ in range(4)]
            q.model.exogenous[0].probability_ppm[:]=[rand.randrange(100001,899999),0]
            q.model.exogenous[0].probability_ppm[1]=1_000_000-q.model.exogenous[0].probability_ppm[0]
            f,r=go(q)
            self.assertEqual(r.status,p.EXACT_MODEL_RESULT)
            self.assertTrue(verify_causal_result(f,r.SerializeToString(deterministic=True)))

if __name__=='__main__':unittest.main()
