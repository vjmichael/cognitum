"""G9 deterministic and independent-reference statistical/failure-path tests."""
import copy
import unittest
import math
import numpy as np
from scipy.stats import bootstrap
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8
from tools import run_c14_p4e_g9_interval_comparison as g9

class G9Numerics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,_=g7.make_fixture('observed_heterogeneous',1001,300)
        cls.report=g9.conduct(seeds=(1001,1002,1003),sizes=(300,),resamples=199)

    def test_g8_wald_unchanged(self):
        a=g8.stratified_wald_interval(self.data,include_covariate_mix_variation=True)
        b=g9.one_case('observed_heterogeneous',1001,300,resamples=199)['methods']['G8_POPULATION_MIX_WALD']
        self.assertAlmostEqual(a['lower'],b['lower'],places=13)
        self.assertAlmostEqual(a['upper'],b['upper'],places=13)

    def test_fast_statistic_equals_exact_rational_reference(self):
        self.assertAlmostEqual(g9._standardized_from_counts(g9.counted(self.data)),
                               g7.exact_stratified(self.data)['ate'],places=13)

    def test_pairs_sampling_not_separate_columns(self):
        cells=g9.counted(self.data)
        self.assertEqual(sum(cells),len(self.data))
        self.assertEqual(len(cells),8)
        self.assertEqual(int(cells[3]),int(((self.data==[0,1,1]).all(axis=1)).sum()))

    def test_bootstrap_seed_replay(self):
        a=g9.bootstrap_intervals(self.data,seed=444,resamples=199)
        b=g9.bootstrap_intervals(self.data,seed=444,resamples=199)
        self.assertEqual(a,b)
        self.assertEqual(a['status'],'COMPUTED')

    def test_basic_reverse_of_percentile(self):
        o=g9.bootstrap_intervals(self.data,seed=444,resamples=199)
        p=o['methods']['PAIRS_BOOT_PERCENTILE'];q=o['methods']['PAIRS_BOOT_BASIC']
        self.assertAlmostEqual(q['lower'],2*o['estimate']-p['upper'],places=12)
        self.assertAlmostEqual(q['upper'],2*o['estimate']-p['lower'],places=12)

    def test_bca_against_independent_scipy(self):
        o=g9.bootstrap_intervals(self.data,seed=444,resamples=399)
        def reference(z,t,y):return g9._standardized_from_counts(g9.counted(np.column_stack((z,t,y))))
        external=bootstrap(tuple(self.data[:,k] for k in (0,1,2)),reference,
                           paired=True,vectorized=False,method='BCa',n_resamples=399,
                           rng=np.random.default_rng(444))
        # Different bootstrap random-number generators: cross-check statistical
        # magnitude and method, NOT deterministic identity of the two samples.
        ours=o['methods']['PAIRS_BOOT_BCA']
        self.assertLess(abs(ours['lower']-external.confidence_interval.low),.09)
        self.assertLess(abs(ours['upper']-external.confidence_interval.high),.09)

    def test_bca_jackknife_acceleration_reproduced_bruteforce(self):
        o=g9.bootstrap_intervals(self.data,seed=444,resamples=199)
        j=np.array([g9._standardized_from_counts(g9.counted(np.delete(self.data,i,axis=0)))
                    for i in range(len(self.data))])
        m=j.mean();diff=m-j
        a=np.sum(diff**3)/(6*np.sum(diff**2)**1.5)
        self.assertAlmostEqual(a,o['bca_acceleration'],places=10)

    def test_aipw_seed_replay(self):
        a=g9.aipw_crossfit(self.data,seed=101)
        self.assertEqual(a,g9.aipw_crossfit(self.data,seed=101))
        self.assertEqual(a['crossfit_folds'],2)
        self.assertFalse('causal_verified' in a)

    def test_double_robust_nuisance_options(self):
        for p,m in [('stratified','stratified'),('stratified','pooled'),('pooled','stratified'),('pooled','pooled')]:
            out=g9.aipw_crossfit(self.data,seed=110,propensity_spec=p,outcome_spec=m)
            self.assertEqual(out['status'],'COMPUTED')
            self.assertTrue(math.isfinite(out['estimate']))
            self.assertLess(out['lower'],out['upper'])
        with self.assertRaises(ValueError):g9.aipw_crossfit(self.data,seed=110,propensity_spec='neural_fiction')

    def test_no_overlap_fail_closed(self):
        r=g9.one_case('no_overlap',1001,300,resamples=199)
        self.assertTrue(all(v['status']!='COMPUTED' for v in r['methods'].values()))
        self.assertTrue(r['partial_identification_envelope_contains_truth'])

    def test_confounding_not_coverage(self):
        s=self.report['summary']['hidden_confounder@300']
        self.assertTrue(all(not v['causal_coverage_eligible'] and v['empirical_coverage'] is None for v in s.values()))

    def test_coverage_wilson_uncertainty_not_nominal_guarantee(self):
        self.assertEqual(g9.wilson_interval(0,0),None)
        low,high=g9.wilson_interval(95,100)
        self.assertLess(low,.95);self.assertGreater(high,.95)

    def test_report_replay(self):
        self.assertTrue(g9.verify_report(self.report))

    def test_forged_interval_rejected(self):
        x=copy.deepcopy(self.report)
        x['results'][0]['methods']['G8_POPULATION_MIX_WALD']['lower']=-.999
        self.assertFalse(g9.verify_report(x))

    def test_forged_coverage_rejected(self):
        x=copy.deepcopy(self.report)
        x['summary']['observed_heterogeneous@300']['PAIRS_BOOT_BCA']['empirical_coverage']=1.
        self.assertFalse(g9.verify_report(x))

    def test_forged_causal_approval_rejected(self):
        x=copy.deepcopy(self.report);x['claims']['host_authorized']=True
        self.assertFalse(g9.verify_report(x))

    def test_bad_budgets(self):
        with self.assertRaises(ValueError):g9.conduct(seeds=(123,123),sizes=(300,),resamples=199)
        with self.assertRaises(ValueError):g9.bootstrap_intervals(self.data,seed=123,resamples=5)

if __name__=='__main__': unittest.main()
