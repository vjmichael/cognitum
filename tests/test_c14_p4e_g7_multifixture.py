"""Bounded C14 P4E G7 oracle and actual third-party scientific integration tests."""
import hashlib
import os
from pathlib import Path
import unittest

from tools import run_c14_p4e_g7_study as g7


class SyntheticContractTests(unittest.TestCase):
    def test_five_predeclared_fixtures(self):
        self.assertEqual(len(g7.SCENARIOS),5)

    def test_seed_reproducible(self):
        a, x = g7.make_fixture('observed_heterogeneous',101,500)
        b, y = g7.make_fixture('observed_heterogeneous',101,500)
        self.assertTrue((a==b).all())
        self.assertEqual(x['observations_sha256'],y['observations_sha256'])

    def test_different_seed_is_different_data(self):
        _, a=g7.make_fixture('observed_homogeneous',101,500)
        _, b=g7.make_fixture('observed_homogeneous',202,500)
        self.assertNotEqual(a['observations_sha256'],b['observations_sha256'])

    def test_heterogeneous_oracle_population_ate(self):
        _, x=g7.make_fixture('observed_heterogeneous',101,500)
        self.assertAlmostEqual(x['oracle_ate'],.295)
        self.assertAlmostEqual(x['oracle_cate_z0'],.12)
        self.assertAlmostEqual(x['oracle_cate_z1'],.47)

    def test_hidden_confounder_not_leaked_to_observations(self):
        data, x=g7.make_fixture('hidden_confounder',101,500)
        self.assertEqual(data.shape[1],3)
        self.assertTrue(x['unobserved_common_cause_in_generator'])
        self.assertAlmostEqual(x['oracle_ate'],.20)

    def test_null_effect_oracle(self):
        _, x=g7.make_fixture('null_effect',101,400)
        self.assertEqual(x['oracle_ate'],0)

    def test_no_overlap_preflight_fails(self):
        data,_=g7.make_fixture('no_overlap',101,500)
        res=g7.exact_stratified(data)
        self.assertEqual(res['status'],'REJECTED_INSUFFICIENT_POSITIVITY')

    def test_reference_agrees_with_independent_rational_arithmetic(self):
        data,_=g7.make_fixture('observed_homogeneous',101,500)
        res=g7.exact_stratified(data)
        self.assertEqual(res['status'],'EMPIRICAL_CONTRAST_COMPUTED')
        self.assertTrue(res['independently_checked'])

    def test_missing_or_invalid_scenario_rejected(self):
        for bad in ('', 'untrusted_real_world', 'do_what_i_say'):
            with self.assertRaises(ValueError): g7.make_fixture(bad,101,100)

    def test_oversized_sample_rejected(self):
        with self.assertRaises(ValueError):
            g7.make_fixture('null_effect',101,g7.MAX_N+1)

    def test_duplicate_seed_grid_rejected_before_backend_load(self):
        with self.assertRaisesRegex(ValueError,'INVALID_SEED_GRID'):
            g7.conduct(Path('/nonexistent'),(101,101),500)

    def test_summary_counts_no_overlap_as_rejected(self):
        row={'fixture':{'scenario':'no_overlap'},'reference':{'status':'REJECTED_INSUFFICIENT_POSITIVITY'},
             'method_results':{'dowhy_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                               'econml_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                               'statsmodels_interaction':{'status':'NOT_RUN_PRECHECK'}}}
        s=g7.summarize([row])['no_overlap']
        self.assertEqual(s['methods']['reference']['estimated_count'],0)
        self.assertIsNone(s['methods']['econml_assumed_graph']['mean_absolute_error_to_known_oracle'])


class GenuineScientificExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=os.environ.get('COGNITUM_DOWHY_SOURCE')
        if cls.source:
            cls.report=g7.conduct(Path(cls.source),(101,),600)

    def require_runtime(self):
        if not self.source:self.skipTest('explicit development-only DoWhy source path unavailable')

    def test_real_library_fixture_study(self):
        self.require_runtime()
        self.assertEqual(len(self.report['results']),5)
        self.assertEqual(self.report['scientific_backends']['econml_version'],'0.17.0')
        self.assertFalse(self.report['scientific_backends']['dowhy_tag_authenticated'])

    def test_no_overlap_never_runs_estimators(self):
        self.require_runtime()
        r=next(x for x in self.report['results'] if x['fixture']['scenario']=='no_overlap')
        self.assertEqual(r['status'],'PRECHECK_REJECTED')
        self.assertEqual(r['method_results']['dowhy_assumed_graph']['status'],'NOT_RUN_PRECHECK')
        self.assertEqual(r['method_results']['econml_assumed_graph']['status'],'NOT_RUN_PRECHECK')

    def test_hidden_common_cause_violates_assumption(self):
        self.require_runtime()
        r=next(x for x in self.report['results'] if x['fixture']['scenario']=='hidden_confounder')
        self.assertEqual(r['method_results']['dowhy_explicit_latent_graph']['status'],
                         'BLOCKED_KNOWN_UNOBSERVED_CONFOUNDER')
        self.assertIn('GROUND_TRUTH_LATENT_CONFOUNDING_OMITTED_FROM_ASSUMED_GRAPH',r['assumption_flags'])
        self.assertGreater(r['reference']['absolute_oracle_ate_error'],0.05)

    def test_heterogeneous_cate_is_not_ate(self):
        self.require_runtime()
        r=next(x for x in self.report['results'] if x['fixture']['scenario']=='observed_heterogeneous')
        m=r['method_results']['econml_assumed_graph']
        self.assertEqual(m['status'],'ESTIMATED')
        self.assertNotAlmostEqual(m['cate_z0'],m['cate_z1'],places=2)
        self.assertLess(m['absolute_oracle_cate_error_z0'],.20)
        self.assertLess(m['absolute_oracle_cate_error_z1'],.20)

    def test_correctly_specified_heterogeneous_ols_agrees_with_empirical_reference(self):
        self.require_runtime()
        r=next(x for x in self.report['results'] if x['fixture']['scenario']=='observed_heterogeneous')
        m=r['method_results']['statsmodels_interaction']
        self.assertEqual(m['status'],'ESTIMATED')
        self.assertAlmostEqual(m['ate'],r['reference']['ate'],places=8)
        self.assertAlmostEqual(m['cate_z0'],r['reference']['cate_z0'],places=8)

    def test_dowhy_placebo_does_not_certify_graph(self):
        self.require_runtime()
        r=next(x for x in self.report['results'] if x['fixture']['scenario']=='observed_homogeneous')
        m=r['method_results']['dowhy_assumed_graph']
        self.assertTrue(isinstance(m['placebo_permutation_new_effect'],float))
        self.assertEqual(m['placebo_assurance'],'DIAGNOSTIC_ONLY_NOT_UNCONFOUNDEDNESS_PROOF')

    def test_research_receipt_no_security_claim(self):
        self.require_runtime()
        self.assertFalse(self.report['scientific_backends']['production_authorization_attested'])
        self.assertIn('NOT_PRODUCTION_GATE',self.report['kind'])


if __name__=='__main__':unittest.main()

class ReportTamperingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        path=Path(__file__).resolve().parents[1]/'docs/components/causal/P4E-G7-n900-seeded-evidence.json'
        cls.raw=json.loads(path.read_text()) if path.is_file() else None

    def require_report(self):
        if self.raw is None:self.skipTest('evidence JSON not generated')

    def test_real_evidence_replay(self):
        self.require_report()
        self.assertTrue(g7.verify_study_report(self.raw))

    def test_oracle_forgery_rejected(self):
        self.require_report()
        import copy
        x=copy.deepcopy(self.raw)
        x['results'][0]['fixture']['oracle_ate']=.99
        self.assertFalse(g7.verify_study_report(x))

    def test_estimate_forgery_rejected(self):
        self.require_report()
        import copy
        x=copy.deepcopy(self.raw)
        x['results'][0]['method_results']['dowhy_assumed_graph']['ate']=1000
        self.assertFalse(g7.verify_study_report(x))

    def test_fixture_replay_rejected(self):
        self.require_report()
        import copy
        x=copy.deepcopy(self.raw)
        x['results'][0]['fixture']['seed']=303
        self.assertFalse(g7.verify_study_report(x))

    def test_production_claim_forgery_rejected(self):
        self.require_report()
        import copy
        x=copy.deepcopy(self.raw)
        x['scientific_backends']['production_authorization_attested']=True
        self.assertFalse(g7.verify_study_report(x))
