"""C14 P4D: genuine statsmodels diagnostic and negative-gate tests."""
import math
import random
import unittest
from unittest.mock import patch
from cognitum.proto import causal_temporal_advanced_pb2 as d
from cognitum.causal_temporal_advanced import (
    run_temporal_advanced_frame,temporal_advanced_receipt)
from tests.test_c14_p4c_temporal_diagnostics import case


def request(seed=43):
    return d.TemporalAdvancedRequest(schema_version=1,samples=case(seed=seed),
                                     adf_maxlag=2,timeout_ms=5000)


def execute(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=run_temporal_advanced_frame(raw,**kw)
    return raw,d.TemporalAdvancedResult.FromString(reply),reply


class TestAdvancedTemporal(unittest.TestCase):
    def test_actual_statsmodels_baseline(self):
        import statsmodels
        raw,got,reply=execute(request(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,d.ADV_COMPUTED,got.reason_code)
        self.assertEqual(got.backend_id,'statsmodels-adf-kpss-cusum')
        self.assertEqual(got.backend_version,statsmodels.__version__)
        self.assertEqual(len(got.diagnostics),2)
        self.assertTrue(got.regular_cadence_checked)
        self.assertTrue(temporal_advanced_receipt(raw,reply).same_backend_replay_checked)
        self.assertFalse(got.causal_directions_verified)
        self.assertFalse(got.statistical_assumptions_verified)
    def test_values_match_real_library_directly(self):
        from statsmodels.tsa.stattools import adfuller,kpss
        from statsmodels.stats.diagnostic import breaks_cusumolsresid
        import numpy as np
        req=request()
        _,res,_=execute(req,host_authorized=True,enabled=True)
        for v in res.diagnostics:
            arr=np.asarray([row.values[v.variable] for row in req.samples.observations])
            expected_adf=adfuller(arr,maxlag=2,regression='c',autolag=None)
            expected_kpss=kpss(arr,regression='c',nlags='auto')
            expected_cusum=breaks_cusumolsresid(arr-arr.mean(),ddof=1)
            for value,expected in [(v.adf_statistic,expected_adf[0]),
                                   (v.adf_raw_p,expected_adf[1]),
                                   (v.kpss_statistic,expected_kpss[0]),
                                   (v.kpss_raw_p,expected_kpss[1]),
                                   (v.cusum_statistic,expected_cusum[0]),
                                   (v.cusum_raw_p,expected_cusum[1])]:
                self.assertAlmostEqual(float(value),float(expected),places=9)
    def test_multiple_testing_bonferroni(self):
        _,res,_=execute(request(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED)
        for v in res.diagnostics:
            self.assertAlmostEqual(float(v.adf_adjusted_p),min(1,6*float(v.adf_raw_p)),places=9)
            self.assertAlmostEqual(float(v.kpss_adjusted_p),min(1,6*float(v.kpss_raw_p)),places=9)
            self.assertAlmostEqual(float(v.cusum_adjusted_p),min(1,6*float(v.cusum_raw_p)),places=9)
            self.assertTrue(v.stationarity_signal.endswith(('NOT_PROOF','INCONCLUSIVE','REJECTIONS')))
    def test_stationary_noise_signal_is_not_proof(self):
        req=request();rng=random.Random(123)
        for row in req.samples.observations:
            row.values[:]=[rng.gauss(0,1),rng.gauss(0,1)]
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED)
        self.assertTrue(any('STATIONARITY_NOT_PROOF' in x.stationarity_signal for x in res.diagnostics))
        self.assertFalse(res.statistical_assumptions_verified)
    def test_random_walk_does_not_get_proof_of_stationarity(self):
        req=request();rng=random.Random(91);walk=0.
        for row in req.samples.observations:
            walk+=rng.gauss(0,1)
            row.values[0]=walk
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED,res.reason_code)
        self.assertNotEqual(res.diagnostics[0].stationarity_signal,'PATTERN_COMPATIBLE_WITH_LEVEL_STATIONARITY_NOT_PROOF')
    def test_large_mean_shift_flagged(self):
        req=request();rng=random.Random(27)
        for i,row in enumerate(req.samples.observations):
            row.values[0]=(20 if i>=150 else 0)+rng.gauss(0,.4)
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED,res.reason_code)
        self.assertTrue(res.diagnostics[0].possible_mean_instability)
    def test_shifted_time_origin_same_hypothesis_statistics(self):
        r1=request();r2=request()
        for row in r2.samples.observations:row.timestamp_ms+=50000
        _,o1,_=execute(r1,host_authorized=True,enabled=True)
        _,o2,_=execute(r2,host_authorized=True,enabled=True)
        self.assertEqual([x.SerializeToString() for x in o1.diagnostics],
                         [x.SerializeToString() for x in o2.diagnostics])
    def test_disallow_incomplete_grid_without_imputation(self):
        req=request();del req.samples.observations[100]
        raw,res,reply=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_INCONCLUSIVE)
        self.assertEqual(res.reason_code,'NONREGULAR_TIMESTAMPS_NO_INTERPOLATION')
        self.assertFalse(temporal_advanced_receipt(raw,reply).same_backend_replay_checked)
    def test_disallow_off_grid_jitter(self):
        req=request();req.samples.observations[101].timestamp_ms+=1
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_INCONCLUSIVE)
    def test_duplicate_timestamp(self):
        req=request();req.samples.observations[2].timestamp_ms=req.samples.observations[1].timestamp_ms
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
        self.assertIn('TIMESTAMP',res.reason_code)
    def test_constant_rejected_inconclusive(self):
        req=request()
        for row in req.samples.observations:row.values[0]=1.
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_INCONCLUSIVE)
        self.assertEqual(res.reason_code,'CONSTANT_OR_DEGENERATE_SERIES')
    def test_disabled_by_default(self):
        _,res,_=execute(request())
        self.assertEqual(res.status,d.ADV_REJECTED)
        self.assertEqual(res.reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_host_denied_even_if_enabled(self):
        _,res,_=execute(request(),enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_enabled_required_separately(self):
        _,res,_=execute(request(),host_authorized=True)
        self.assertEqual(res.reason_code,'ADV_TEMP_DISABLED')
    def test_invalid_adf_lag(self):
        req=request();req.adf_maxlag=4
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_invalid_schema(self):
        req=request();req.schema_version=2
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_too_short_samples(self):
        req=request();del req.samples.observations[:225]
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_nan_rejected(self):
        req=request();req.samples.observations[1].values[0]=float('nan')
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_noncanonical_unknown_field(self):
        raw=request().SerializeToString(deterministic=True)+b'\xc0\x0c\x01'
        res=d.TemporalAdvancedResult.FromString(run_temporal_advanced_frame(raw,host_authorized=True,enabled=True))
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_oversized_frame(self):
        res=d.TemporalAdvancedResult.FromString(run_temporal_advanced_frame(b'z'*260001,host_authorized=True,enabled=True))
        self.assertEqual(res.status,d.ADV_REJECTED)
    def test_forged_pvalue_rejected(self):
        raw,res,_=execute(request(),host_authorized=True,enabled=True)
        res.diagnostics[0].adf_raw_p='0'
        self.assertFalse(temporal_advanced_receipt(raw,res.SerializeToString(deterministic=True)).same_backend_replay_checked)
    def test_forged_stationarity_proof_rejected(self):
        raw,res,_=execute(request(),host_authorized=True,enabled=True)
        res.statistical_assumptions_verified=True
        self.assertFalse(temporal_advanced_receipt(raw,res.SerializeToString(deterministic=True)).same_backend_replay_checked)
    def test_forged_causal_claim_rejected(self):
        raw,res,_=execute(request(),host_authorized=True,enabled=True)
        res.causal_directions_verified=True
        self.assertFalse(temporal_advanced_receipt(raw,res.SerializeToString(deterministic=True)).same_backend_replay_checked)
    def test_cross_request_replay_rejected(self):
        raw1,_,reply=execute(request(43),host_authorized=True,enabled=True)
        raw2,_,_=execute(request(44),host_authorized=True,enabled=True)
        self.assertNotEqual(raw1,raw2)
        self.assertFalse(temporal_advanced_receipt(raw2,reply).same_backend_replay_checked)
    def test_p4c_unchanged_and_independently_host_gated(self):
        from cognitum.causal_temporal_diagnostics import run_temporal_diagnostics_frame
        from cognitum.proto import causal_temporal_diagnostics_pb2 as c
        _,res,_=execute(request(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED)
        origin=case().SerializeToString(deterministic=True)
        denied=c.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(origin))
        self.assertEqual(denied.status,c.TEMP_DIAG_REJECTED)
    def test_real_backend_unavailability_explicit(self):
        import builtins
        real=builtins.__import__
        def block(name,*a,**kw):
            if name.startswith('statsmodels'):
                raise ImportError('synthetic offline missing dependency')
            return real(name,*a,**kw)
        with patch('builtins.__import__',side_effect=block):
            _,res,_=execute(request(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_BACKEND_UNAVAILABLE)
        self.assertEqual(res.reason_code,'STATSMODELS_NUMERICAL_BACKEND_UNAVAILABLE')
    def test_declared_interval_mismatch(self):
        req=request();req.samples.declared_interval_ms=100
        _,res,_=execute(req,host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_INCONCLUSIVE)
    def test_kpss_boundary_flag_is_not_numeric_certainty(self):
        _,res,_=execute(request(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.ADV_COMPUTED)
        self.assertTrue(any(x.kpss_table_boundary for x in res.diagnostics))

if __name__=='__main__':unittest.main()
