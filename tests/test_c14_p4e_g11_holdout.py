"""G11: frozen-G10 holdout evaluation, shift stress, and typed fail-closed gate."""
import copy, hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import run_c14_p4e_g11_holdout as study
from cognitum import causal_assurance_policy as g10,causal_holdout_assurance as g11
from cognitum.proto import causal_holdout_assurance_pb2 as pb
from tests.test_c14_p4e_g10_assurance_policy import req


def sample(scenario='observed_heterogeneous',method='PAIRS_BOOT_BCA',n=300,domain=g11.KNOWN_SYNTHETIC_DOMAIN):
    a=req(scenario,method,n=n,resamples=399)
    d,r=g10.calculate(a)
    return pb.HoldoutAssuranceRequest(schema_version=1,trace_id='G11-test',upstream_request=a,
        upstream_decision=d,upstream_receipt=r,declared_evaluation_domain=domain)


class HoldoutPolicyTests(unittest.TestCase):
    def assert_read_only(self,d):
        self.assertTrue(d.research_only)
        self.assertFalse(d.may_issue_real_world_causal_claim)
        self.assertFalse(d.may_recommend_intervention)
        self.assertFalse(d.may_trigger_external_action)
        self.assertFalse(d.authenticated_lu_host)

    def test_bca_small_heterogeneous_describe_synthetic_only(self):
        q=sample();d,r=g11.calculate(q)
        self.assertEqual(d.disposition,'DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY')
        self.assertEqual(d.holdout_completed,194)
        self.assertTrue(d.recorded_holdout_coverage)
        self.assert_read_only(d);self.assertTrue(g11.verify(q,d,r))

    def test_small_heterogeneous_wald_cannot_upgrade_g10(self):
        q=sample(method='G8_POPULATION_MIX_WALD');d,r=g11.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_UPSTREAM_G10')
        self.assertTrue(g11.verify(q,d,r))

    def test_aipw_900_hetero_downgraded_by_holdout(self):
        q=sample(method='AIPW_CROSSFIT_IF_WALD',n=900);d,r=g11.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_HOLDOUT_CALIBRATION')
        self.assertAlmostEqual(d.holdout_empirical_coverage,.92)
        self.assertIn('WILSON_LOWER_BOUND_BELOW_PRELIMINARY_THRESHOLD',d.reason_codes)
        self.assertTrue(g11.verify(q,d,r))

    def test_hidden_confounder_no_upgrade(self):
        q=sample(scenario='hidden_confounder');d,r=g11.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_UPSTREAM_G10')
        self.assertFalse(d.recorded_holdout_coverage)
        self.assert_read_only(d);self.assertTrue(g11.verify(q,d,r))

    def test_absent_overlap_no_upgrade(self):
        q=sample(scenario='no_overlap');d,r=g11.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_UPSTREAM_G10');self.assert_read_only(d)

    def test_unknown_domain_abstains(self):
        for domain in ['','UNKNOWN','REAL_WORLD','SHIFTED_SYNTHETIC']:
            with self.subTest(domain=domain):
                q=sample(domain=domain);d,r=g11.calculate(q)
                self.assertEqual(d.disposition,'ABSTAIN_DISTRIBUTION_UNKNOWN_OR_SHIFTED')
                self.assert_read_only(d);self.assertTrue(g11.verify(q,d,r))

    def test_shuffled_g10_result_rejected(self):
        q=sample();q.upstream_decision.disposition=1
        d,r=g11.calculate(q);self.assertEqual(d.disposition,'REJECT_UNVERIFIED')
        self.assertIn('UPSTREAM_G10_REPLAY_FAILED',d.reason_codes)

    def test_forged_upstream_receipt_rejected(self):
        q=sample();q.upstream_receipt.authenticated_lu_host=True
        d,_=g11.calculate(q);self.assertEqual(d.disposition,'REJECT_UNVERIFIED')

    def test_cross_request_replay_rejected(self):
        q=sample();d,r=g11.calculate(q)
        q2=copy.deepcopy(q);q2.trace_id='changed'
        self.assertFalse(g11.verify(q2,d,r))

    def test_forged_action_bit_rejected(self):
        q=sample();d,r=g11.calculate(q)
        for attr in ('may_issue_real_world_causal_claim','may_recommend_intervention','may_trigger_external_action','authenticated_lu_host'):
            with self.subTest(attr=attr):
                bad=copy.deepcopy(d);setattr(bad,attr,True)
                self.assertFalse(g11.verify(q,bad,r))

    def test_tampered_holdout_evidence_denied(self):
        q=sample()
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/'evidence.json';fake.write_text('{}')
            with patch.object(g11,'REPORT_PATH',fake):
                d,r=g11.calculate(q)
                self.assertEqual(d.disposition,'REJECT_UNVERIFIED')
                self.assertTrue(g11.verify(q,d,r))

    def test_missing_report_denied(self):
        q=sample()
        with patch.object(g11,'REPORT_PATH',Path('/no-such-report-g11.json')):
            d,_=g11.calculate(q);self.assertEqual(d.disposition,'REJECT_UNVERIFIED')

    def test_changed_upstream_policy_does_not_get_trusted(self):
        q=sample()
        with patch.object(g11,'FROZEN_G10_SHA256','0'*64):
            d,_=g11.calculate(q);self.assertEqual(d.disposition,'REJECT_UNVERIFIED')

    def test_invalid_proto_input(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TYPED_HOLDOUT_REQUEST'):
            g11.calculate(pb.HoldoutAssuranceRequest())

    def test_typed_roundtrip(self):
        q=sample();d,r=g11.calculate(q)
        self.assertEqual(q,pb.HoldoutAssuranceRequest.FromString(q.SerializeToString()))
        self.assertEqual(d,pb.HoldoutAssuranceDecision.FromString(d.SerializeToString()))
        self.assertEqual(r,pb.HoldoutAssuranceReceipt.FromString(r.SerializeToString()))

    def test_shift_fixture_has_adjusted_heterogeneous_oracle(self):
        rows,info=study.shifted_fixture('observed_heterogeneous',61001,900)
        self.assertEqual(rows.shape,(900,3))
        self.assertAlmostEqual(info['oracle_ate'],.4)
        self.assertAlmostEqual(info['z_probability'],.8)
        self.assertGreater(rows[:,0].mean(),.7)

    def test_holdout_and_training_seeds_do_not_overlap(self):
        self.assertFalse(set(study.HOLDOUT_SEEDS)&set(range(2001,2201)))
        self.assertFalse(set(study.HOLDOUT_SEEDS)&set(study.SHIFT_SEEDS))

    def test_seed_collision_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'HOLDOUT_SEED_PARTITION_VIOLATION'):
            study.conduct(holdout_seeds=(2001,),shift_seeds=(61001,))

    def test_shift_bootstrap_low_completion_not_ignored(self):
        r=json.loads(g11.REPORT_PATH.read_text())
        e=r['shifted_summary']['observed_heterogeneous@300']['PAIRS_BOOT_BCA']
        self.assertLess(e['computed'],e['attempts']*.95)
        self.assertEqual(e['G11_disposition'],'ABSTAIN_DISTRIBUTION_SHIFT')
        self.assertFalse(e['G9_calibration_applicable'])

    def test_independent_report_replay_selected_cases(self):
        r=json.loads(g11.REPORT_PATH.read_text())
        self.assertEqual(r['counts'],{'holdout_datasets':2000,'shifted_datasets':600})
        self.assertEqual(hashlib.sha256(g11.REPORT_PATH.read_bytes()).hexdigest(),g11.PINNED_G11_SHA256)
        for scenario,n,seed in [('observed_heterogeneous',300,51001),('null_effect',900,51199),('hidden_confounder',300,51010)]:
            case=study.g9.one_case(scenario,seed,n,resamples=399)
            self.assertEqual(case['fixture']['scenario'],scenario)
        self.assertTrue(r['holdout_summary']['observed_heterogeneous@900']['AIPW_CROSSFIT_IF_WALD']['empirical_coverage']<.925)

if __name__=='__main__':unittest.main()
