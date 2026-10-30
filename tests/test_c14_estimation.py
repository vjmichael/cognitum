"""C14 P2A observational adjustment: synthetic math and hostile frames."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import unittest

from cognitum.causal_estimation import (run_estimation_frame, verify_estimation_result,
                                          estimation_receipt, estimation_audit)
from cognitum.proto import causal_pb2 as p, causal_estimation_pb2 as q


def request():
    m=p.StructuralCausalModel(assumption_id='synthetic-graph-not-verified',
        exogenous=[p.ExogenousVariable(id='U',states=['u0','u1'],probability_ppm=[500000,500000]),
                   p.ExogenousVariable(id='V',states=['v0','v1'],probability_ppm=[500000,500000])],
        endogenous=[
            p.EndogenousVariable(id='Z',states=['no','yes'],noise=[0],function_outputs=[0,1]),
            p.EndogenousVariable(id='X',states=['no','yes'],parents=[0],noise=[1],function_outputs=[0,1,1,0]),
            p.EndogenousVariable(id='Y',states=['no','yes'],parents=[0,1],function_outputs=[0,1,1,1]),
        ])
    return q.EstimationRequest(schema_version=1,trace_id='c14-p2a',
        identification=p.CausalRequest(schema_version=1,trace_id='c14-p2a',operation=p.BACKDOOR_CHECK,
          model=m,treatment=1,target=2,adjustment=[0],max_exogenous_assignments=128,timeout_ms=1000),
        observations=[
            q.FrequencyRow(states=[0,0,0],count=30),
            q.FrequencyRow(states=[0,1,1],count=30),
            q.FrequencyRow(states=[1,0,1],count=20),
            q.FrequencyRow(states=[1,1,1],count=20),
        ],backend=q.REFERENCE_STRATIFIED_ADJUSTMENT,min_arm_count=2,timeout_ms=1000)


def go(req, *, authorized=True, enabled=True):
    raw=req.SerializeToString(deterministic=True)
    reply=run_estimation_frame(raw,host_authorized=authorized,enabled=enabled)
    return raw,q.EstimationResult.FromString(reply),reply

class C14P2ATests(unittest.TestCase):
    def test_exact_adjustment(self):
        raw,result,reply=go(request())
        self.assertEqual(result.status,q.ADJUSTED_EFFECT_COMPUTED)
        self.assertEqual(result.estimate,'3/5')
        self.assertEqual(result.total_observations,100)
        self.assertEqual([s.observed_weight for s in result.strata],['3/5','2/5'])
        self.assertEqual((result.leave_one_stratum_out_min,result.leave_one_stratum_out_max),('0','1'))
        self.assertTrue(result.graph_criterion_checked)
        self.assertTrue(result.independently_checked)
        self.assertTrue(verify_estimation_result(raw,reply))
        self.assertTrue(estimation_receipt(raw,reply).computation_verified)

    def test_no_adjustment_in_graph_with_confounder_denied(self):
        r=request();r.identification.adjustment.clear()
        self.assertEqual(go(r)[1].status,q.ADJUSTMENT_NOT_CERTIFIED)

    def test_hidden_common_cause_cannot_adjust(self):
        r=request();y=r.identification.model.endogenous[2]
        y.noise.append(1)
        y.function_outputs[:]=[0,0,1,1,1,1,1,1]
        self.assertEqual(go(r)[1].status,q.ADJUSTMENT_NOT_CERTIFIED)

    def test_unobserved_positivity(self):
        r=request();del r.observations[2]
        self.assertEqual(go(r)[1].status,q.POSITIVITY_NOT_MET)

    def test_small_arm_is_not_accepted(self):
        r=request();r.observations[2].count=1
        self.assertEqual(go(r)[1].status,q.POSITIVITY_NOT_MET)

    def test_zero_treatment_or_outcome_is_binary_requirement(self):
        r=request();r.identification.model.endogenous[2].states.append('maybe')
        r.identification.model.endogenous[2].function_outputs[:]=[0,1,1,1]
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_ci_for_mixed_binary_data(self):
        r=request();r.observations.clear();r.observations.extend([
            q.FrequencyRow(states=[0,0,0],count=15), q.FrequencyRow(states=[0,0,1],count=15),
            q.FrequencyRow(states=[0,1,0],count=6),q.FrequencyRow(states=[0,1,1],count=24),
            q.FrequencyRow(states=[1,0,0],count=6),q.FrequencyRow(states=[1,0,1],count=14),
            q.FrequencyRow(states=[1,1,0],count=2),q.FrequencyRow(states=[1,1,1],count=18),
        ])
        raw,result,reply=go(r)
        # Z=0 effect 0.3, Z=1 effect 0.2 => 0.26.
        self.assertEqual(Fraction(result.estimate),Fraction(13,50))
        self.assertGreater(float(result.standard_error),0)
        self.assertLess(float(result.ci95_lower),float(Fraction(result.estimate)))
        self.assertGreater(float(result.ci95_upper),float(Fraction(result.estimate)))
        self.assertTrue(verify_estimation_result(raw,reply))

    def test_unadjusted_randomized_model_reference(self):
        r=request()
        r.identification.model.endogenous[1].parents.clear()
        r.identification.model.endogenous[1].function_outputs[:]=[0,1]
        r.identification.model.endogenous[2].parents[:]=[1]
        r.identification.model.endogenous[2].function_outputs[:]=[0,1]
        r.identification.adjustment.clear()
        raw,res,reply=go(r)
        self.assertEqual(res.status,q.ADJUSTED_EFFECT_COMPUTED)
        self.assertEqual(res.estimate,'3/5') # empirical marginal difference
        self.assertTrue(verify_estimation_result(raw,reply))

    def test_missing_dowhy_not_fabricated(self):
        r=request();r.backend=q.DOWHY_OPTIONAL_WORKER
        raw,res,reply=go(r)
        self.assertEqual(res.status,q.ESTIMATION_BACKEND_UNAVAILABLE)
        self.assertFalse(estimation_receipt(raw,reply).computation_verified)

    def test_host_denied(self):
        raw,res,reply=go(request(),authorized=False)
        self.assertEqual(res.status,q.ESTIMATION_REJECTED)
        self.assertEqual(res.reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertFalse(estimation_receipt(raw,reply).computation_verified)

    def test_disabled_by_default(self):
        r=request();raw=r.SerializeToString(deterministic=True)
        res=q.EstimationResult.FromString(run_estimation_frame(raw))
        self.assertEqual(res.status,q.ESTIMATION_REJECTED)

    def test_duplicate_rows_not_double_counted(self):
        r=request();r.observations.append(copy.deepcopy(r.observations[0]))
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_invalid_state_not_accepted(self):
        r=request();r.observations[0].states[0]=5
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_zero_count_not_accepted(self):
        r=request();r.observations[0].count=0
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_count_cap(self):
        r=request();r.observations[0].count=200000
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_no_identification_request(self):
        r=request();r.identification.operation=p.INTERVENTIONAL_QUERY
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_mismatched_trace(self):
        r=request();r.identification.trace_id='another'
        self.assertEqual(go(r)[1].status,q.ESTIMATION_REJECTED)

    def test_forged_estimate(self):
        raw,res,reply=go(request());res.estimate='17/19'
        self.assertFalse(verify_estimation_result(raw,res.SerializeToString(deterministic=True)))

    def test_forged_ci(self):
        raw,res,reply=go(request());res.ci95_upper='17'
        self.assertFalse(verify_estimation_result(raw,res.SerializeToString(deterministic=True)))

    def test_forged_assurance(self):
        raw,res,reply=go(request());res.assurance='REAL_WORLD_CAUSAL_EFFECT_PROVEN'
        self.assertFalse(verify_estimation_result(raw,res.SerializeToString(deterministic=True)))

    def test_cross_request_replay(self):
        raw,res,reply=go(request());other=request();other.observations[0].count+=1
        self.assertFalse(verify_estimation_result(other.SerializeToString(deterministic=True),reply))

    def test_metadata_audit_no_dataset_rows(self):
        raw,res,reply=go(request());audit=estimation_audit(raw,reply)
        self.assertEqual(audit.request_sha256,hashlib.sha256(raw).digest())
        self.assertEqual(audit.result_sha256,hashlib.sha256(reply).digest())
        self.assertNotIn(b'synthetic-graph-not-verified',audit.SerializeToString())

    def test_model_unknown_field_rejected(self):
        r=request()
        data=r.SerializeToString(deterministic=True)+b'\xc0\x0c\x01'
        res=q.EstimationResult.FromString(run_estimation_frame(data,host_authorized=True,enabled=True))
        self.assertEqual(res.status,q.ESTIMATION_REJECTED)

    def test_source_graph_not_replaced_with_false_empirical_authority(self):
        _,res,_=go(request())
        self.assertEqual(res.assurance,'SUPPLIED_GRAPH_EMPIRICAL_ADJUSTMENT')
        self.assertIn('NOT_EMPIRICALLY_VERIFIED',res.reason_code)

if __name__=='__main__':unittest.main()
