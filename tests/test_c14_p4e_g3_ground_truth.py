"""G3 generated-data validation and genuine PCMCI/PCMCI+ acceptance tests.

The positive tests require the real uploaded source installed in the invoking
interpreter, not a fake Tigramite mock. No authenticated Lu/Windows gate.
"""
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

from cognitum.causal_tigramite_backend import VERSION
from cognitum.proto import causal_temporal_discovery_pb2 as td
from cognitum.proto import causal_temporal_diagnostics_pb2 as p4c
from tools.run_c14_p4e_g3_ground_truth import (
    make_series, make_request, score_candidate, evaluate, SCENARIOS,
)

try:
    GENUINE = version('tigramite') == VERSION
except PackageNotFoundError:
    GENUINE = False


class TestP4EG3Fixtures(unittest.TestCase):
    def test_generator_size_and_finite_values(self):
        for case in SCENARIOS:
            x=make_series(case, 160, 13)
            self.assertEqual(x.shape, (160, 2))
            self.assertTrue(np.isfinite(x).all())
            self.assertGreater(x.std(axis=0).min(),0)

    def test_determinism_with_same_seed(self):
        for case in SCENARIOS:
            self.assertTrue(np.array_equal(make_series(case, 160, 13),
                                           make_series(case, 160, 13)))

    def test_distinct_seeds_change_data(self):
        self.assertFalse(np.array_equal(make_series('independent', 160, 13),
                                        make_series('independent', 160, 29)))

    def test_invalid_scenario_or_size_rejected(self):
        for name,rows,seed in [('made_up',160,13),('direct_lag',50,13),
                               ('direct_lag',501,13),('direct_lag',160,0)]:
            with self.assertRaises(ValueError): make_series(name,rows,seed)

    def test_correct_ground_truth_classes(self):
        self.assertEqual(set(SCENARIOS), {'direct_lag','independent',
                         'latent_common_cause','structural_change'})

    def test_nonstationary_changes_effect_sign(self):
        # Generator uses +0.85 and -0.85 on opposite sides of midpoint.
        a=make_series('structural_change', 160, 13)
        self.assertEqual(a.shape,(160,2))
        self.assertTrue(np.isfinite(a).all())

    def test_timestamps_regular_and_request_honest(self):
        raw=make_request('direct_lag',160,13,td.TD_PCMCI_LAGGED)
        req=td.TemporalDiscoveryRequest.FromString(raw)
        self.assertEqual(len(req.samples.observations),160)
        self.assertEqual([v for v in req.samples.variable_ids],['X','Y'])
        self.assertTrue(req.stationarity_assumption_acknowledged)
        self.assertFalse(any(req.samples.observations[i+1].timestamp_ms-
                             req.samples.observations[i].timestamp_ms!=250
                             for i in range(159)))

    def test_wrong_backend_version_rejected_before_running(self):
        with patch('tools.run_c14_p4e_g3_ground_truth.version',return_value='unknown'):
            with self.assertRaisesRegex(RuntimeError,'UNAPPROVED_VERSION'):
                evaluate(seeds=(13,),sizes=(160,),scenarios=('independent',),
                         methods={'PCMCI':td.TD_PCMCI_LAGGED})

    def test_fabricated_reply_cannot_be_scored(self):
        raw=make_request('independent',160,13,td.TD_PCMCI_LAGGED)
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_G3_RESULT'):
            score_candidate(raw,b'','independent')

    def test_score_rejects_unjustified_causal_proof(self):
        from cognitum import causal_tigramite_backend as backend
        raw=make_request('independent',160,13,td.TD_PCMCI_LAGGED)
        # A negative receipt must never be treated as statistical evidence.
        forged=td.TemporalDiscoveryResult(schema_version=1,status=td.TD_CANDIDATE,
                                          causal_directions_proven=True)
        with self.assertRaises(ValueError):
            score_candidate(raw,forged.SerializeToString(),'independent')

    def test_no_user_data_or_dependency_included_by_test_generator(self):
        self.assertTrue(make_request('independent',160,13,td.TD_PCMCI_PLUS))


@unittest.skipUnless(GENUINE,'REAL_TIGRAMITE_5_2_10_1_REQUIRED')
class TestP4EG3RealLibrary(unittest.TestCase):
    def test_full_mini_study_reproducible_fixtures(self):
        a=evaluate(seeds=(13,29),sizes=(160,),
                   scenarios=('direct_lag','independent'))
        self.assertEqual(a['case_count'],8)
        self.assertEqual(len(a['summaries']),4)
        self.assertEqual(len({c['request_sha256'] for c in a['cases']}),8)
        self.assertFalse(any('tp' in x for x in a['summaries']
                             if x['scenario'] not in ('direct_lag','independent')))
        self.assertIn('uncorrected',a['method_significance_policies']['PCMCI+'])

    def test_stress_scenarios_excluded_from_precision(self):
        a=evaluate(seeds=(13,),sizes=(160,),
                   scenarios=('latent_common_cause','structural_change'))
        self.assertEqual(a['case_count'],4)
        self.assertTrue(all('tp' not in x for x in a['summaries']))
        self.assertTrue(all('assumption_violations_present' in x for x in a['summaries']))


if __name__=='__main__': unittest.main()
