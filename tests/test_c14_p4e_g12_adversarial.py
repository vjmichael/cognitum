"""G12 fresh synthetic mechanisms + independent numeric and typed assurance checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cognitum import causal_adversarial_assurance as g12
from cognitum import causal_g12_independent_verifier as independent
from tools import run_c14_p4e_g12_adversarial as study
from cognitum import causal_holdout_assurance as g11
from cognitum.proto import causal_adversarial_assurance_pb2 as pb
from tests.test_c14_p4e_g11_holdout import sample


def request(case='CLEAN_INTERACTION',n=300,upstream_method='PAIRS_BOOT_BCA'):
    upstream=sample(method=upstream_method)
    d,r=g11.calculate(upstream)
    return pb.AdversarialAssuranceRequest(schema_version=1,trace_id='g12-test',
        upstream_request=upstream,upstream_decision=d,upstream_receipt=r,
        study_scenario=case,study_sample_size=n)


class StudyAndIndependentVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads(g12.REPORT_PATH.read_text())

    def test_all_960_recomputed_from_counts(self):
        self.assertEqual(independent.verify_report(self.report)['records_verified'],960)

    def test_clean_adjustment_reduces_bias(self):
        for n in study.SIZES:
            s=self.report['summary'][f'CLEAN_INTERACTION@{n}']
            self.assertLess(s['mean_absolute_stratified_error'],s['mean_absolute_naive_error']/3)

    def test_hidden_confounder_persists(self):
        for n in study.SIZES:
            s=self.report['summary'][f'HIDDEN_COMMON_CAUSE@{n}']
            self.assertGreater(s['mean_absolute_stratified_error'],.25)

    def test_mismeasurement_not_cured(self):
        self.assertGreater(self.report['summary']['MISMEASURED_CONFOUNDER@900']['mean_absolute_stratified_error'],.25)

    def test_selection_collider_failure(self):
        self.assertGreater(self.report['summary']['SELECTION_COLLIDER@900']['mean_absolute_naive_error'],.5)

    def test_transport_shift_has_new_oracle(self):
        self.assertEqual(study.ORACLES['TRANSPORT_SHIFT'],.39)
        self.assertGreater(abs(study.ORACLES['TRANSPORT_SHIFT']-.25),.1)

    def test_null_effect_is_zero(self):
        self.assertEqual(study.ORACLES['NEGATIVE_CONTROL'],0.)

    def test_different_seed_family(self):
        self.assertFalse(set(study.SEEDS)&set(range(2001,2201)))
        self.assertFalse(set(study.SEEDS)&set(range(51001,51201)))

    def test_generator_replay_first_and_last(self):
        for scenario in study.SCENARIOS:
            for n in study.SIZES:
                for seed in (study.SEEDS[0],study.SEEDS[-1]):
                    record=next(r for r in self.report['records'] if (r['scenario'],r['sample_size'],r['seed'])==(scenario,n,seed))
                    self.assertEqual(study.generate(scenario,seed,n),record['counts_z_t_y'])

    def test_forged_naive_estimate(self):
        r=copy.deepcopy(self.report);r['records'][0]['naive_risk_difference']+=.2
        with self.assertRaisesRegex(ValueError,'G12_NAIVE_RESULT_MISMATCH'):independent.verify_report(r)

    def test_forged_adjusted_estimate(self):
        r=copy.deepcopy(self.report);r['records'][0]['stratified_risk_difference']+=.2
        with self.assertRaisesRegex(ValueError,'G12_STRATIFIED_RESULT_MISMATCH'):independent.verify_report(r)

    def test_forged_counts(self):
        r=copy.deepcopy(self.report);r['records'][0]['counts_z_t_y'][0]+=1
        with self.assertRaisesRegex(ValueError,'G12_ORACLE_OR_SAMPLE_MISMATCH'):independent.verify_report(r)

    def test_forged_oracle(self):
        r=copy.deepcopy(self.report);r['records'][0]['oracle_ate']=.99
        with self.assertRaisesRegex(ValueError,'G12_ORACLE_OR_SAMPLE_MISMATCH'):independent.verify_report(r)

    def test_duplicate_record(self):
        r=copy.deepcopy(self.report);r['records'][1]=r['records'][0]
        with self.assertRaisesRegex(ValueError,'G12_DUPLICATE_OR_OUT_OF_DESIGN_RECORD'):independent.verify_report(r)

    def test_aggregate_falsification(self):
        r=copy.deepcopy(self.report);r['summary']['CLEAN_INTERACTION@300']['mean_absolute_stratified_error']=0.
        with self.assertRaisesRegex(ValueError,'G12_AGGREGATE_MATH_MISMATCH'):independent.verify_report(r)

    def test_claim_of_real_world_authority_rejected(self):
        r=copy.deepcopy(self.report);r['claims']['intervention_authorized']=True
        with self.assertRaisesRegex(ValueError,'FALSE_G12_CAUSAL_AUTHORITY'):independent.verify_report(r)

    def test_unsafe_count_types_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_SUFFICIENT_COUNTS'):
            independent.independent_counts_check([True]+[0]*7)

    def test_out_of_scope_seed(self):
        with self.assertRaisesRegex(ValueError,'NONREGISTERED_G12_FIXTURE'):study.generate('CLEAN_INTERACTION',2001,300)


class G12AdmissionTests(unittest.TestCase):
    def test_clean_case_still_abstains_new_domain(self):
        q=request();d,r=g12.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_NEW_UNCALIBRATED_GENERATOR')
        self.assertEqual(d.studied_datasets,80)
        self.assertTrue(d.independent_evidence_math_verified)
        self.assertTrue(d.may_describe_synthetic_stress_diagnostic)
        self.assertTrue(g12.verify(q,d,r))

    def test_adversarial_cases_abstain(self):
        for case in g12.ADVERSARIAL:
            with self.subTest(case=case):
                q=request(case);d,r=g12.calculate(q)
                self.assertEqual(d.disposition,'ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION')
                self.assertFalse(d.may_recommend_intervention)
                self.assertTrue(g12.verify(q,d,r))

    def test_upstream_abstention_never_upgraded(self):
        q=request(upstream_method='G8_POPULATION_MIX_WALD');d,r=g12.calculate(q)
        self.assertEqual(d.disposition,'ABSTAIN_UPSTREAM');self.assertFalse(d.may_describe_synthetic_stress_diagnostic);self.assertTrue(g12.verify(q,d,r))

    def test_unknown_case_fails_closed(self):
        q=request('UNKNOWN');d,r=g12.calculate(q)
        self.assertEqual(d.disposition,'REJECT_UNVERIFIED');self.assertFalse(d.independent_evidence_math_verified)
        self.assertTrue(g12.verify(q,d,r))

    def test_bad_request_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_G12_TYPED_REQUEST'):g12.calculate(pb.AdversarialAssuranceRequest())

    def test_forged_upstream(self):
        q=request();q.upstream_decision.authenticated_lu_host=True
        d,r=g12.calculate(q)
        self.assertEqual(d.disposition,'REJECT_UNVERIFIED')
        self.assertTrue(g12.verify(q,d,r))

    def test_cross_request_replay(self):
        q=request();d,r=g12.calculate(q)
        q2=copy.deepcopy(q);q2.trace_id='someone-else'
        self.assertFalse(g12.verify(q2,d,r))

    def test_request_to_intervene_is_not_authorized(self):
        q=request();q.requests_intervention_recommendation=True
        d,r=g12.calculate(q)
        self.assertIn('REQUESTED_INTERVENTION_NEVER_AUTHORIZED',d.reason_codes)
        self.assertFalse(d.may_recommend_intervention);self.assertTrue(g12.verify(q,d,r))

    def test_forged_action_flags(self):
        q=request();d,r=g12.calculate(q)
        for attr in ('may_issue_real_world_causal_claim','may_recommend_intervention','may_trigger_external_action','authenticated_lu_host'):
            forged=copy.deepcopy(d);setattr(forged,attr,True)
            self.assertFalse(g12.verify(q,forged,r))

    def test_forged_result_metric(self):
        q=request();d,r=g12.calculate(q)
        d.naive_mean_absolute_error=0.
        self.assertFalse(g12.verify(q,d,r))

    def test_tampered_report_fails_closed(self):
        q=request()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'report.json';p.write_text('{}')
            with patch.object(g12,'REPORT_PATH',p):
                d,r=g12.calculate(q)
                self.assertEqual(d.disposition,'REJECT_UNVERIFIED')
                self.assertTrue(g12.verify(q,d,r))

    def test_g11_source_pin_fails_closed(self):
        q=request()
        with patch.object(g12,'PINNED_G11_SOURCE_SHA256','0'*64):
            d,r=g12.calculate(q)
            self.assertEqual(d.disposition,'REJECT_UNVERIFIED')
            self.assertTrue(g12.verify(q,d,r))

    def test_protobuf_round_trip(self):
        q=request();d,r=g12.calculate(q)
        self.assertEqual(q,pb.AdversarialAssuranceRequest.FromString(q.SerializeToString()))
        self.assertEqual(d,pb.AdversarialAssuranceDecision.FromString(d.SerializeToString()))
        self.assertEqual(r,pb.AdversarialAssuranceReceipt.FromString(r.SerializeToString()))


if __name__=='__main__':unittest.main()
