"""C14 P4C: actual observation timestamp preflight and residual checks."""
import random
import unittest
from cognitum.causal_temporal_diagnostics import (
    run_temporal_diagnostics_frame, temporal_diagnostics_receipt,
    make_screen_from_regular_timestamps)
from cognitum.proto import causal_temporal_diagnostics_pb2 as d
from cognitum.proto import causal_temporal_pb2 as a
from tests.test_c14_p4a_temporal import case as p4a_case


def case(seed=43,lag=1):
    old=p4a_case(seed=seed,lags=lag)
    request=d.TemporalDiagnosticRequest(
        schema_version=1,trace_id='p4c-timestamp-check',variable_ids=old.variable_ids,
        declared_interval_ms=250,max_lag=lag,familywise_alpha=.01,timeout_ms=5000)
    for index,row in enumerate(old.observations):
        request.observations.add(timestamp_ms=10000+index*250,values=row.values)
    return request


def evaluate(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=run_temporal_diagnostics_frame(raw,**kw)
    return raw,d.TemporalDiagnosticResult.FromString(reply),reply

class TestP4CTemporalDiagnostics(unittest.TestCase):
    def test_regular_timestamp_and_residuals(self):
        raw,out,reply=evaluate(case(),host_authorized=True,enabled=True)
        self.assertEqual(out.status,d.TEMP_DIAG_COMPUTED,out.reason_code)
        self.assertEqual(out.cadence,d.TEMP_CADENCE_REGULAR)
        self.assertTrue(out.regular_cadence_checked)
        self.assertTrue(out.eligible_for_fixed_lag_screen)
        self.assertEqual(out.observed_samples,300)
        self.assertEqual((out.min_interval_ms,out.max_interval_ms),(250,250))
        self.assertEqual((out.irregular_intervals,out.missing_grid_slots),(0,0))
        self.assertEqual(len(out.residual_tests),2)
        self.assertTrue(temporal_diagnostics_receipt(raw,reply).numerical_replay_checked)
        self.assertFalse(out.statistical_assumptions_verified)
        self.assertFalse(out.causal_directions_verified)
    def test_replay_each_residual(self):
        raw,out,reply=evaluate(case(),host_authorized=True,enabled=True)
        for entry in out.residual_tests:
            self.assertGreaterEqual(float(entry.bonferroni_p),float(entry.raw_p))
            self.assertLessEqual(float(entry.bonferroni_p),1.0)
            self.assertEqual(entry.tested_lags,5)
            self.assertGreaterEqual(float(entry.ljung_box_q),0)
    def test_p4a_bridge_with_exact_regular_cadence(self):
        req=case();raw,out,reply=evaluate(req,host_authorized=True,enabled=True)
        old=a.TemporalScreenRequest.FromString(make_screen_from_regular_timestamps(raw,reply))
        self.assertEqual(old.interval_ms,250)
        self.assertEqual(old.max_lag,1)
        self.assertEqual(len(old.observations),300)
        self.assertEqual(list(old.observations[0].values),list(req.observations[0].values))
        self.assertEqual(old.trace_id,req.trace_id)
    def test_p4a_still_host_denied_even_after_bridge(self):
        from cognitum.causal_temporal import run_temporal_frame
        raw,_,reply=evaluate(case(),host_authorized=True,enabled=True)
        screen=make_screen_from_regular_timestamps(raw,reply)
        result=a.TemporalScreenResult.FromString(run_temporal_frame(screen))
        self.assertEqual(result.status,a.TEMPORAL_REJECTED)
    def test_missing_grid_points(self):
        req=case();del req.observations[100]
        raw,res,reply=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual((res.cadence,res.missing_grid_slots),(d.TEMP_CADENCE_GAPPED,1))
        self.assertEqual(res.irregular_intervals,1)
        self.assertFalse(res.eligible_for_fixed_lag_screen)
        self.assertEqual(len(res.residual_tests),0)
        self.assertTrue(temporal_diagnostics_receipt(raw,reply).numerical_replay_checked)
        with self.assertRaises(ValueError):make_screen_from_regular_timestamps(raw,reply)
    def test_many_missing_grid_points(self):
        req=case();del req.observations[101:108]
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.missing_grid_slots,7)
    def test_off_grid_sampling(self):
        req=case()
        for i in range(100,len(req.observations)):
            req.observations[i].timestamp_ms+=13
        raw,res,reply=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.cadence,d.TEMP_CADENCE_IRREGULAR)
        self.assertGreater(res.irregular_intervals,0)
        self.assertEqual(res.reason_code,'OFF_GRID_IRREGULAR_SAMPLING_BLOCKED')
        self.assertFalse(res.eligible_for_fixed_lag_screen)
        self.assertFalse(len(res.residual_tests))
        self.assertTrue(temporal_diagnostics_receipt(raw,reply).numerical_replay_checked)
    def test_slight_jitter_rejected_no_interpolation(self):
        req=case();req.observations[150].timestamp_ms+=1
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.cadence,d.TEMP_CADENCE_IRREGULAR)
        self.assertFalse(res.eligible_for_fixed_lag_screen)
        self.assertIn('NO_IMPUTATION',res.assumptions_and_limits)
    def test_alternate_time_origin_invariant_cadence(self):
        req=case()
        for row in req.observations:row.timestamp_ms+=10000000
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.cadence,d.TEMP_CADENCE_REGULAR)
    def test_false_sampling_declaration_not_accepted(self):
        req=case();req.declared_interval_ms=200
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.cadence,d.TEMP_CADENCE_IRREGULAR)
    def test_default_denied(self):
        _,res,_=evaluate(case())
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
        self.assertEqual(res.reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled(self):
        _,res,_=evaluate(case(),host_authorized=True)
        self.assertEqual(res.reason_code,'TEMP_DIAGNOSTICS_DISABLED')
    def test_permission_not_bypassed_by_enabled(self):
        _,res,_=evaluate(case(),enabled=True)
        self.assertEqual(res.reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_duplicate_timestamp_rejected(self):
        req=case();req.observations[22].timestamp_ms=req.observations[21].timestamp_ms
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
        self.assertEqual(res.reason_code,'NONMONOTONIC_OR_DUPLICATE_TIMESTAMPS')
    def test_out_of_order_timestamp_rejected(self):
        req=case();req.observations[22].timestamp_ms=1
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_nan_rejected(self):
        req=case();req.observations[0].values[0]=float('nan')
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.reason_code,'INVALID_TEMP_DIAG_OBSERVATIONS')
    def test_wrong_row_shape_rejected(self):
        req=case();req.observations[0].values.append(1)
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_invalid_alpha_rejected(self):
        req=case();req.familywise_alpha=.99
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_short_data_rejected(self):
        req=case();del req.observations[0:250]
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_collinearity_not_approved(self):
        req=case()
        for row in req.observations:row.values[1]=row.values[0]
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_INCONCLUSIVE)
        self.assertFalse(res.eligible_for_fixed_lag_screen)
    def test_strong_residual_autocorrelation_flagged(self):
        req=case();r=random.Random(991);u=y=0.
        # Y is an AR(2) process but the requested regression only includes lag 1.
        history=[0.,0.]
        for row in req.observations:
            x=r.gauss(0,1)
            y=.85*history[-2]+r.gauss(0,.3)
            history.append(y);history.pop(0)
            row.values[0]=x;row.values[1]=y
        _,res,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.TEMP_DIAG_COMPUTED,res.reason_code)
        self.assertTrue(any(q.reject_white_noise for q in res.residual_tests))
        self.assertFalse(res.eligible_for_fixed_lag_screen)
    def test_forged_eligibility_rejected(self):
        raw,res,_=evaluate(case(),host_authorized=True,enabled=True)
        res.eligible_for_fixed_lag_screen=False
        reply=res.SerializeToString(deterministic=True)
        self.assertFalse(temporal_diagnostics_receipt(raw,reply).numerical_replay_checked)
        with self.assertRaises(ValueError):make_screen_from_regular_timestamps(raw,reply)
    def test_forged_causal_claim_rejected(self):
        raw,res,_=evaluate(case(),host_authorized=True,enabled=True)
        res.causal_directions_verified=True
        self.assertFalse(temporal_diagnostics_receipt(raw,res.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_forged_statistical_assumption_claim_rejected(self):
        raw,res,_=evaluate(case(),host_authorized=True,enabled=True)
        res.statistical_assumptions_verified=True
        self.assertFalse(temporal_diagnostics_receipt(raw,res.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_forged_p_value_rejected(self):
        raw,res,_=evaluate(case(),host_authorized=True,enabled=True)
        res.residual_tests[0].raw_p='0'
        self.assertFalse(temporal_diagnostics_receipt(raw,res.SerializeToString(deterministic=True)).numerical_replay_checked)
    def test_cross_request_replay_rejected(self):
        raw1,_,reply=evaluate(case(seed=43),host_authorized=True,enabled=True)
        raw2,_,_=evaluate(case(seed=44),host_authorized=True,enabled=True)
        self.assertFalse(temporal_diagnostics_receipt(raw2,reply).numerical_replay_checked)
        self.assertNotEqual(raw1,raw2)
    def test_oversized_frame_rejected(self):
        res=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(b'x'*250001,host_authorized=True,enabled=True))
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_unknown_field_rejected(self):
        raw=case().SerializeToString(deterministic=True)+b'\xc0\x0c\x01'
        res=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(raw,host_authorized=True,enabled=True))
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)
    def test_invalid_request_frame_rejected(self):
        res=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(b'garbage',host_authorized=True,enabled=True))
        self.assertEqual(res.status,d.TEMP_DIAG_REJECTED)

if __name__=='__main__':unittest.main()

class TestP4CIndependentBaseline(unittest.TestCase):
    """Actual statsmodels diagnostic cross-check (optional external package)."""
    def test_ljung_box_against_statsmodels(self):
        try:
            import numpy as np
            from statsmodels.stats.diagnostic import acorr_ljungbox
        except ImportError:
            self.skipTest('optional statsmodels baseline unavailable')
        req=case()
        raw,out,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(out.status,d.TEMP_DIAG_COMPUTED)
        data=np.array([row.values for row in req.observations],dtype=float)
        lag=req.max_lag
        design=np.column_stack([np.ones(len(data)-lag)]+[
            data[lag-k:len(data)-k,j] for k in range(1,lag+1) for j in range(2)])
        for item in out.residual_tests:
            y=data[lag:,item.variable]
            resid=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
            expected=acorr_ljungbox(resid,lags=[item.tested_lags],
                                    model_df=lag,return_df=True)
            self.assertAlmostEqual(float(item.ljung_box_q),float(expected.lb_stat.iloc[0]),places=7)
            self.assertAlmostEqual(float(item.raw_p),float(expected.lb_pvalue.iloc[0]),places=7)
    def test_installed_baseline_not_mandatory_for_engine(self):
        req=case();raw,out,reply=evaluate(req,host_authorized=True,enabled=True)
        self.assertTrue(temporal_diagnostics_receipt(raw,reply).numerical_replay_checked)
        self.assertFalse(out.statistical_assumptions_verified)
