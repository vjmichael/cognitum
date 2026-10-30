"""G10 fail-closed assurance: receipts are NOT authority or causal identification."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cognitum import causal_interval_comparison as g9_wire
from cognitum import causal_assurance_policy as policy
from cognitum.proto import causal_interval_comparison_pb2 as gp
from cognitum.proto import causal_assurance_policy_pb2 as pb


def req(scenario='observed_heterogeneous', method='G8_POPULATION_MIX_WALD', n=300, seed=1001,
        confidence=.95, recommend=False, resamples=199):
    exp = gp.IntervalComparisonRequest(schema_version=1, trace_id='g10-experiment', scenario=scenario,
        seed=seed, sample_size=n, bootstrap_resamples=resamples, confidence=confidence)
    result, receipt = g9_wire.calculate(exp)
    return pb.CausalAssuranceRequest(schema_version=1, trace_id='g10-trace', experiment=exp,
        candidate=result, calculation_receipt=receipt, selected_method=method,
        requests_intervention_recommendation=recommend)


class AssurancePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good = req('null_effect', n=900)
        cls.hetero = req()
        cls.hidden = req('hidden_confounder')
        cls.no_overlap = req('no_overlap')

    def assert_never_authority(self, outcome):
        self.assertTrue(outcome.research_only)
        self.assertFalse(outcome.causal_assumptions_verified)
        self.assertFalse(outcome.may_issue_causal_claim)
        self.assertFalse(outcome.may_recommend_intervention)
        self.assertFalse(outcome.may_trigger_external_action)
        self.assertFalse(outcome.authenticated_lu_host)

    def test_mature_calibration_descriptive_only(self):
        o,receipt=policy.calculate(self.good)
        self.assertEqual(o.disposition, pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY)
        self.assert_never_authority(o)
        self.assertTrue(o.calculation_replay_checked)
        self.assertTrue(o.calibration.recorded_calibration)
        self.assertTrue(policy.verify(self.good,o,receipt))
        self.assertEqual(o.calibration.completed,200)
        self.assertLess(o.calibration.wilson_lower,o.calibration.nominal_confidence)

    def test_small_sample_heterogeneous_wald_undercoverage(self):
        o,r=policy.calculate(self.hetero)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION)
        self.assertIn('EMPIRICAL_SYNTHETIC_UNDERCOVERAGE',o.reason_codes)
        self.assertAlmostEqual(o.calibration.observed_coverage,.915)
        self.assertTrue(policy.verify(self.hetero,o,r))

    def test_hidden_confounder_blocks_point_causal_claim(self):
        o,r=policy.calculate(self.hidden)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_ABSTAIN_CONFOUNDING)
        self.assertFalse(o.calibration.recorded_calibration)
        self.assertTrue(o.partial_bounds.available)
        self.assertFalse(o.partial_bounds.point_identified)
        self.assert_never_authority(o)
        self.assertTrue(policy.verify(self.hidden,o,r))

    def test_no_overlap_is_different_reason(self):
        o,r=policy.calculate(self.no_overlap)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_ABSTAIN_POSITIVITY)
        self.assertFalse(o.calibration.recorded_calibration)
        self.assertTrue(o.partial_bounds.available)
        self.assertTrue(policy.verify(self.no_overlap,o,r))

    def test_bounds_are_distinct_from_point_interval(self):
        o,_=policy.calculate(self.hidden)
        b=o.partial_bounds
        self.assertLessEqual(b.population_envelope_lower,b.plug_in_identified_lower)
        self.assertGreaterEqual(b.population_envelope_upper,b.plug_in_identified_upper)
        self.assertIn('PARTIAL_IDENTIFICATION',b.interpretation)

    def test_requesting_intervention_does_not_increase_authority(self):
        q=copy.deepcopy(self.good);q.requests_intervention_recommendation=True
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY)
        self.assertIn('INTERVENTION_AUTHORITY_NEVER_GRANTED',o.reason_codes)
        self.assert_never_authority(o)
        self.assertTrue(policy.verify(q,o,r))

    def test_untrusted_candidate_interval_tampering_rejected(self):
        q=copy.deepcopy(self.good);q.candidate.methods[0].lower=-99
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)
        self.assertFalse(o.calculation_replay_checked)
        self.assertTrue(policy.verify(q,o,r))

    def test_cross_request_replay_is_rejected(self):
        q=copy.deepcopy(self.good);q.experiment.seed=1235
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)
        self.assertTrue(policy.verify(q,o,r))

    def test_forged_receipt_rejected(self):
        q=copy.deepcopy(self.good);q.calculation_receipt.host_authenticated=True
        o,_=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)

    def test_forged_result_never_verifies(self):
        o,r=policy.calculate(self.good);o.may_trigger_external_action=True
        self.assertFalse(policy.verify(self.good,o,r))

    def test_forged_disposition_never_verifies(self):
        o,r=policy.calculate(self.hetero);o.disposition=pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY
        self.assertFalse(policy.verify(self.hetero,o,r))

    def test_cross_request_policy_receipt_fails(self):
        o,r=policy.calculate(self.good)
        q=copy.deepcopy(self.good);q.trace_id='different'
        self.assertFalse(policy.verify(q,o,r))

    def test_evidence_archive_corruption_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json';p.write_text('{}')
            with patch.object(policy,'EVIDENCE_PATH',p):
                o,r=policy.calculate(self.good)
                self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)
                self.assertIn('CALIBRATION_SOURCE_NOT_VERIFIED_OR_MISSING',o.reason_codes)
                self.assertTrue(policy.verify(self.good,o,r))

    def test_missing_calibration_report_denied(self):
        with patch.object(policy,'EVIDENCE_PATH',Path('/nonexistent/causal-report.json')):
            o,_=policy.calculate(self.good)
            self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)

    def test_calibration_mismatched_nominal_confidence_denied(self):
        q=req('null_effect',n=900,confidence=.90)
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION)
        self.assertTrue(policy.verify(q,o,r))

    def test_unknown_selected_method_rejected(self):
        q=copy.deepcopy(self.good);q.selected_method='MIRACLE_ESTIMATOR'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_METHOD'):policy.calculate(q)

    def test_missing_evidence_rejected(self):
        q=copy.deepcopy(self.good);q.ClearField('candidate')
        with self.assertRaisesRegex(ValueError,'MISSING_CALCULATION_EVIDENCE'):policy.calculate(q)

    def test_bootstrap_calibration_requires_matching_resamples(self):
        q=req('observed_heterogeneous','PAIRS_BOOT_BCA',n=300,resamples=199)
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION)
        self.assertIn('INSUFFICIENT_APPLICABLE_CALIBRATION',o.reason_codes)
        self.assertTrue(policy.verify(q,o,r))

    def test_proto_roundtrip(self):
        q=self.good
        self.assertEqual(q,pb.CausalAssuranceRequest.FromString(q.SerializeToString()))
        o,r=policy.calculate(q)
        self.assertEqual(o,pb.CausalAssuranceDecision.FromString(o.SerializeToString()))
        self.assertEqual(r,pb.CausalAssuranceReceipt.FromString(r.SerializeToString()))

    def test_no_verification_from_standalone_receipt(self):
        o,r=policy.calculate(self.good);r.authenticated_lu_host=True
        self.assertFalse(policy.verify(self.good,o,r))

    def test_bootstrap_method_also_policy_checked(self):
        q=req('observed_heterogeneous','PAIRS_BOOT_BCA',n=300,resamples=399)
        o,r=policy.calculate(q)
        self.assertEqual(o.disposition,pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY)
        self.assertEqual(o.calibration.completed,196)
        self.assertEqual(o.calibration.attempts,200)
        self.assertTrue(policy.verify(q,o,r))

if __name__=='__main__':unittest.main()
