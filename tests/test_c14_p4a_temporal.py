"""C14 P4A conditional *predictive*, not causal, lagged screening."""
import math
import random
import unittest
from cognitum.proto import causal_temporal_pb2 as t
from cognitum.causal_temporal import run_temporal_frame,temporal_receipt


def case(seed=43,related=True,lags=1):
    r=random.Random(seed)
    req=t.TemporalScreenRequest(schema_version=1,trace_id='p4a-temporal',
        variable_ids=['X','Y'],interval_ms=250,max_lag=lags,
        familywise_alpha=.01,timeout_ms=5000)
    x=y=0.0
    for _ in range(300):
        old_x=x
        x=.5*x+r.gauss(0,1)
        y=.35*y+(.85*old_x if related else 0)+r.gauss(0,.7)
        req.observations.add(values=[x,y])
    return req


def evaluate(req,**kwargs):
    raw=req.SerializeToString(deterministic=True)
    reply=run_temporal_frame(raw,**kwargs)
    return raw,t.TemporalScreenResult.FromString(reply),reply

class TestP4ATemporal(unittest.TestCase):
    def test_predictive_one_lag(self):
        raw,res,reply=evaluate(case(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,t.TEMPORAL_SCREEN_COMPUTED,res.reason_code)
        self.assertEqual(res.tests_executed,2)
        self.assertEqual(res.effective_samples,299)
        effects={(e.source,e.target,e.lag):e for e in res.screens}
        self.assertEqual(set(effects),{(0,1,1),(1,0,1)})
        self.assertTrue(effects[(0,1,1)].passes_familywise_threshold)
        self.assertFalse(effects[(1,0,1)].passes_familywise_threshold)
        self.assertGreater(float(effects[(0,1,1)].coefficient),.4)
        self.assertTrue(temporal_receipt(raw,reply).numerical_replay_checked)
        self.assertFalse(res.time_lagged_causality_verified)
    def test_two_lags_and_adjustment(self):
        _,res,_=evaluate(case(lags=2),host_authorized=True,enabled=True)
        self.assertEqual(res.status,t.TEMPORAL_SCREEN_COMPUTED,res.reason_code)
        self.assertEqual(res.tests_executed,4)
        for e in res.screens:
            p=float(e.unadjusted_p)
            self.assertAlmostEqual(float(e.bonferroni_adjusted_p),min(1,p*4),delta=1e-10)
    def test_independent_negative_control(self):
        _,res,_=evaluate(case(related=False),host_authorized=True,enabled=True)
        self.assertEqual(res.status,t.TEMPORAL_SCREEN_COMPUTED)
        self.assertFalse(any(e.passes_familywise_threshold for e in res.screens))
    def test_different_seed_different_digest(self):
        self.assertNotEqual(evaluate(case(seed=51),host_authorized=True,enabled=True)[1].request_sha256,
                            evaluate(case(seed=44),host_authorized=True,enabled=True)[1].request_sha256)
    def test_disabled(self):
        self.assertEqual(evaluate(case(),host_authorized=True)[1].reason_code,'TEMPORAL_SCREEN_DISABLED')
    def test_denied(self):
        self.assertEqual(evaluate(case(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_no_host_flag_default(self):
        self.assertEqual(evaluate(case())[1].status,t.TEMPORAL_REJECTED)
    def test_invalid_sampling_interval(self):
        req=case();req.interval_ms=0
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_invalid_alpha(self):
        req=case();req.familywise_alpha=.8
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_invalid_lag(self):
        req=case();req.max_lag=4
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_invalid_arity(self):
        req=case();req.variable_ids[1]='X'
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_invalid_nan(self):
        req=case();req.observations[0].values[0]=float('nan')
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_wrong_sample_shape(self):
        req=case();req.observations[0].values.append(2)
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_uninformative_constant_rejected(self):
        req=case()
        for obs in req.observations:obs.values[0]=2
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_INCONCLUSIVE)
    def test_causal_claim_tamper_rejected(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.time_lagged_causality_verified=True
        self.assertFalse(temporal_receipt(raw,got.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_coeff_tamper_rejected(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.screens[0].coefficient='9999999'
        self.assertFalse(temporal_receipt(raw,got.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_wrong_request_digest_rejected(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.request_sha256=b'0'*32
        self.assertFalse(temporal_receipt(raw,got.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_missing_data_short(self):
        req=case();del req.observations[0:250]
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,t.TEMPORAL_REJECTED)
    def test_frame_too_large(self):
        raw=b'b'*180001
        self.assertEqual(t.TemporalScreenResult.FromString(run_temporal_frame(raw,host_authorized=True,enabled=True)).status,t.TEMPORAL_REJECTED)
    def test_no_causal_claim_even_for_strong_predictor(self):
        _,res,_=evaluate(case(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,t.TEMPORAL_SCREEN_COMPUTED)
        self.assertTrue(any(e.passes_familywise_threshold for e in res.screens))
        self.assertFalse(res.time_lagged_causality_verified)
        self.assertIn('NO_CAUSAL_IDENTIFICATION',res.assumptions_and_limits)

if __name__=='__main__':unittest.main()
