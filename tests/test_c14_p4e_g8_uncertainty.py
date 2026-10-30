"""Tests preserve separation of statistical coverage, identification and host security."""
import copy
from pathlib import Path
import unittest
import math
import numpy as np

from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8
from cognitum import causal_uncertainty as wired
from cognitum.proto import causal_uncertainty_pb2 as pb

class PartialIdentificationTests(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):g8.manski_binary_bounds([])
    def test_nonbinary_rejected(self):
        with self.assertRaises(ValueError):g8.manski_binary_bounds([(0,1,1),(1,0,2)])
    def test_invalid_confidence_rejected(self):
        with self.assertRaises(ValueError):g8.manski_binary_bounds([[0,0,0]]*10,.1)
    def test_exact_small_table_bounds(self):
        a=g8.manski_binary_bounds([(0,1,1),(0,1,0),(1,0,1),(1,0,0)])
        self.assertEqual(a['identified_set_plugin_lower'],-.5)
        self.assertEqual(a['identified_set_plugin_upper'],.5)
        self.assertEqual(a['identified_set_width'],1.0)
        self.assertFalse(a['causal_point_identified'])
    def test_always_treated_still_has_bounds(self):
        a=g8.manski_binary_bounds([(0,1,1),(0,1,1),(1,1,1),(1,1,1)])
        self.assertEqual((a['identified_set_plugin_lower'],a['identified_set_plugin_upper']),(0.,1.))
    def test_no_overlap_bounds_do_not_pretend_interval(self):
        d,_=g7.make_fixture('no_overlap',11,250)
        self.assertEqual(g8.stratified_wald_interval(d)['status'],'REJECTED_INSUFFICIENT_POSITIVITY')
        self.assertEqual(g8.manski_binary_bounds(d)['status'],'PARTIALLY_IDENTIFIED_BINARY_OUTCOME')
    def test_conservative_envelope_wider_than_identified_set(self):
        d,_=g7.make_fixture('null_effect',101,300)
        b=g8.manski_binary_bounds(d)
        self.assertLessEqual(b['population_coverage_envelope_lower'],b['identified_set_plugin_lower'])
        self.assertGreaterEqual(b['population_coverage_envelope_upper'],b['identified_set_plugin_upper'])
    def test_point_interval_estimate_matches_g7(self):
        d,_=g7.make_fixture('observed_heterogeneous',101,500)
        self.assertAlmostEqual(g8.stratified_wald_interval(d)['ate'],g7.exact_stratified(d)['ate'])
    def test_population_covariate_mix_variance_is_nonnegative(self):
        d,_=g7.make_fixture('observed_heterogeneous',101,500)
        a=g8.stratified_wald_interval(d)
        b=g8.stratified_wald_interval(d,include_covariate_mix_variation=True)
        self.assertGreaterEqual(b['standard_error'],a['standard_error'])
        self.assertGreaterEqual(b['between_strata_variance_component'],0.0)
        self.assertLessEqual(b['lower'],a['lower'])
        self.assertGreaterEqual(b['upper'],a['upper'])
    def test_smaller_n_wider_hoeffding(self):
        a=g8.manski_binary_bounds([(0,0,0),(1,1,1)]*50)
        b=g8.manski_binary_bounds([(0,0,0),(1,1,1)]*500)
        self.assertGreater(a['envelope_hoeffding_epsilon'],b['envelope_hoeffding_epsilon'])

class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=g8.conduct(tuple(range(101,111)),(300,900))
    def test_full_factorial(self):
        self.assertEqual(len(self.report['results']),100)
    def test_hidden_confounded_not_called_calibrated(self):
        for n in ('300','900'):
            a=self.report['summary'][n]['hidden_confounder']
            self.assertIsNone(a['empirical_point_interval_coverage_on_eligible_cases'])
            self.assertTrue(a['point_coverage_with_invalid_assumptions_is_not_calibration'])
    def test_no_overlap_calibration_not_present(self):
        self.assertIsNone(self.report['summary']['900']['no_overlap']['empirical_point_interval_coverage_on_eligible_cases'])
    def test_clean_samples_eligible(self):
        self.assertEqual(self.report['summary']['900']['observed_homogeneous']['calibration_eligible_cases'],10)
    def test_all_scenarios_have_partial_bounds(self):
        self.assertTrue(all(r['bounds']['identified_set_width']>0.999999 for r in self.report['results']))
    def test_replay_verified(self):
        self.assertTrue(g8.verify_report(self.report))
    def test_replay_rejects_tampered_summary(self):
        a=copy.deepcopy(self.report);a['summary']['900']['null_effect']['cases']=999
        self.assertFalse(g8.verify_report(a))
    def test_replay_rejects_fabricated_causal_assurance(self):
        a=copy.deepcopy(self.report);a['claims']['causal_identification_proven']=True
        self.assertFalse(g8.verify_report(a))
    def test_replay_rejects_changed_estimate(self):
        a=copy.deepcopy(self.report);a['results'][0]['bounds']['identified_set_plugin_lower']=.12345
        self.assertFalse(g8.verify_report(a))
    def test_bad_seed_grid_fails(self):
        with self.assertRaises(ValueError):g8.conduct((12,12),(300,))
    def test_bad_size_grid_fails(self):
        with self.assertRaises(ValueError):g8.conduct((1,),(2,))


def request(scenario='observed_homogeneous',seed=101,n=300):
    d,_=g7.make_fixture(scenario,seed,n)
    r=pb.CausalUncertaintyRequest(schema_version=1,fixture_id=scenario,trace_id='trace-1',confidence=.95,minimum_cell_count=5,
                                  synthetic_oracle_available=True, synthetic_oracle_ate=.24,
                                  known_hidden_confounder=scenario=='hidden_confounder')
    for z,t,y in d:r.observations.add(covariate=bool(z),treatment=bool(t),outcome=bool(y))
    return r

class TypedReceiptTests(unittest.TestCase):
    def test_protobuf_round_trip(self):
        r=request();self.assertEqual(pb.CausalUncertaintyRequest.FromString(r.SerializeToString()),r)
    def test_replay_and_fail_closed_receipt(self):
        r=request();result,receipt=wired.calculate(r)
        self.assertTrue(wired.verify(r,result,receipt))
        self.assertFalse(result.causal_identification_proven)
        self.assertFalse(receipt.authenticated_host_checked)
    def test_forged_result_rejected(self):
        r=request();o,c=wired.calculate(r);o.partial_identification.population_envelope_lower=1.
        self.assertFalse(wired.verify(r,o,c))
    def test_forged_authorization_rejected(self):
        r=request();o,c=wired.calculate(r);c.authenticated_host_checked=True
        self.assertFalse(wired.verify(r,o,c))
    def test_cross_request_replay_rejected(self):
        r=request();o,c=wired.calculate(r);r2=request(seed=202)
        self.assertFalse(wired.verify(r2,o,c))
    def test_hidden_confounder_no_point(self):
        r=request('hidden_confounder');o,c=wired.calculate(r)
        self.assertTrue(wired.verify(r,o,c))
        self.assertFalse(o.point_interval.point_interval_available)
        self.assertEqual(o.point_interval.reason_code,'KNOWN_HIDDEN_CONFOUNDER_POINT_IDENTIFICATION_BLOCKED')
    def test_no_overlap_no_point(self):
        r=request('no_overlap');o,c=wired.calculate(r)
        self.assertFalse(o.point_interval.point_interval_available)
        self.assertGreater(o.partial_identification.identified_upper_plugin,o.partial_identification.identified_lower_plugin)
        self.assertTrue(wired.verify(r,o,c))
    def test_budget(self):
        r=request();r.observations.extend(r.observations[:1]*3000)
        with self.assertRaises(ValueError):wired.calculate(r)
    def test_bad_contract_version(self):
        r=request();r.schema_version=99
        with self.assertRaises(ValueError):wired.calculate(r)
    def test_receipt_does_not_certify_causality(self):
        r=request();o,c=wired.calculate(r);c.causal_conclusion_verified=True
        self.assertFalse(wired.verify(r,o,c))

if __name__=='__main__':unittest.main()
