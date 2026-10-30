"""P3 benchmark fixtures are deterministic; they are NOT model benchmarks."""
import unittest
from tools.benchmark_c07_p3 import diagnostic, sample_events

class P3BenchTests(unittest.TestCase):
    def test_fixture_and_stale_attempt(self):
        a,stale=sample_events(4)
        b,_=sample_events(4)
        self.assertEqual([x.SerializeToString(deterministic=True) for x in a],
                         [x.SerializeToString(deterministic=True) for x in b])
        self.assertEqual(stale.expected_revision,1)
    def test_naive_comparison_is_explicitly_non_equivalent(self):
        report=diagnostic(size=4,repeats=1)
        self.assertTrue(report['replayed_projection_matches'])
        self.assertTrue(report['stale_attempt_rejected_by_C07'])
        self.assertTrue(report['naive_stale_attempt_wrongly_overwrote_claim'])
        self.assertFalse(report['Lu_or_model_executed'])
    def test_unbounded_fixture_refused(self):
        with self.assertRaises(ValueError):sample_events(1000)
