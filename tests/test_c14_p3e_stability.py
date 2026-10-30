"""P3E controlled resampling tests; no tests imply true causal discovery."""
import hashlib
import unittest
import random
from cognitum.proto import causal_stability_pb2 as s, causal_discovery_pb2 as d
from cognitum.causal_stability import run_stability_frame, stability_receipt
from tests.test_c14_p3_discovery import fixture


def case(mode=s.SUBSAMPLE_WITHOUT_REPLACEMENT, seed=23):
    source=fixture(seed=7)
    return s.StabilityRequest(schema_version=1,trace_id=source.trace_id,
        source_request=source,mode=mode,repetitions=4,rows_per_replicate=190,
        fixed_seed=seed,total_test_budget=180,total_timeout_ms=25000,
        permuted_variable=1 if mode==s.SUBSAMPLE_PERMUTED_NULL else 0)


def evaluate(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=run_stability_frame(raw,**kw)
    return raw,s.StabilityResult.FromString(reply),reply

class TestP3E(unittest.TestCase):
    def test_subsample_and_replay(self):
        raw,got,reply=evaluate(case(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,s.STABILITY_COMPUTED,got.reason_code)
        self.assertEqual(len(got.replicates),4)
        self.assertEqual([(e.first,e.second) for e in got.edges],[(0,1),(0,2),(1,2)])
        self.assertTrue(all(0 <= e.selection_count <= 4 for e in got.edges))
        self.assertEqual(got.total_tests,sum(x.tests_executed for x in got.replicates))
        self.assertTrue(stability_receipt(raw,reply).exact_resampling_replay)
        self.assertFalse(stability_receipt(raw,reply).causal_model_verified)
        self.assertFalse(got.causal_effect_identified)
        self.assertFalse(got.causal_orientation_established)
    def test_bootstrap_and_replay(self):
        raw,got,reply=evaluate(case(s.BOOTSTRAP_WITH_REPLACEMENT),host_authorized=True,enabled=True)
        self.assertEqual(got.status,s.STABILITY_COMPUTED,got.reason_code)
        self.assertTrue(stability_receipt(raw,reply).exact_resampling_replay)
    def test_permuted_null_and_replay(self):
        raw,got,reply=evaluate(case(s.SUBSAMPLE_PERMUTED_NULL),host_authorized=True,enabled=True)
        self.assertEqual(got.status,s.STABILITY_COMPUTED,got.reason_code)
        self.assertTrue(stability_receipt(raw,reply).exact_resampling_replay)
        self.assertIn('NULL_SHUFFLE',got.assumptions_and_limits)
    def test_different_seeds_change_digests(self):
        _,a,_=evaluate(case(seed=27),host_authorized=True,enabled=True)
        _,b,_=evaluate(case(seed=53),host_authorized=True,enabled=True)
        self.assertEqual((a.status,b.status),(s.STABILITY_COMPUTED,s.STABILITY_COMPUTED))
        self.assertNotEqual(a.replicates[0].draw_indices_sha256,b.replicates[0].draw_indices_sha256)
    def test_denied(self):
        _,got,_=evaluate(case(),enabled=True)
        self.assertEqual(got.reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertFalse(got.edges)
    def test_disabled_default(self):
        _,got,_=evaluate(case(),host_authorized=True)
        self.assertEqual(got.reason_code,'STABILITY_DISABLED')
    def test_non_reference_method_denied(self):
        req=case();req.source_request.method=d.CAUSAL_LEARN_PC_OPTIONAL
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,s.STABILITY_REJECTED)
    def test_invalid_replicates(self):
        for v in (0,1,17):
            with self.subTest(reps=v):
                req=case();req.repetitions=v
                self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,s.STABILITY_REJECTED)
    def test_invalid_sample_count(self):
        for v in (0,59,251,500):
            req=case();req.rows_per_replicate=v
            self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,s.STABILITY_REJECTED)
    def test_invalid_null_column(self):
        req=case(s.SUBSAMPLE_PERMUTED_NULL);req.permuted_variable=3
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'INVALID_PERMUTATION_COLUMN')
    def test_non_null_column_rejected(self):
        req=case();req.permuted_variable=1
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'PERMUTATION_COLUMN_ONLY_FOR_NULL')
    def test_trace_mismatch(self):
        req=case();req.trace_id='other'
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,s.STABILITY_REJECTED)
    def test_budget_insufficient(self):
        req=case();req.total_test_budget=2
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'INSUFFICIENT_TOTAL_TEST_BUDGET')
    def test_budget_exhausted_no_partial_result(self):
        req=case();req.total_test_budget=4
        _,got,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(got.status,s.STABILITY_RESOURCE_LIMIT)
        self.assertEqual(len(got.edges),0)
        self.assertEqual(len(got.replicates),0)
    def test_tampered_receipt_rejected(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.edges[0].selection_count+=1
        self.assertFalse(stability_receipt(raw,got.SerializeToString(deterministic=True)).exact_resampling_replay)
    def test_forged_causation_rejected(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.causal_effect_identified=True
        self.assertFalse(stability_receipt(raw,got.SerializeToString(deterministic=True)).exact_resampling_replay)
    def test_mutated_input_rejected(self):
        raw,got,reply=evaluate(case(),host_authorized=True,enabled=True)
        req=case();req.source_request.observations[0].values[0]+=0.01
        self.assertFalse(stability_receipt(req.SerializeToString(deterministic=True),reply).exact_resampling_replay)
    def test_oversized_frame(self):
        got=s.StabilityResult.FromString(run_stability_frame(b'a'*180001,enabled=True,host_authorized=True))
        self.assertEqual(got.status,s.STABILITY_REJECTED)
    def test_nonfinite_input(self):
        req=case();req.source_request.observations[0].values[0]=float('nan')
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,s.STABILITY_REJECTED)
    def test_no_partial_on_degenerate_sample(self):
        req=case();
        for row in req.source_request.observations:row.values[0]=2
        _,got,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(got.status,s.STABILITY_INCONCLUSIVE)
        self.assertEqual(len(got.edges),0)
if __name__=='__main__':unittest.main()
