"""T4 P3 red-team audit contract tests. Test references are SYNTHETIC, never lab evidence."""
import hashlib
import math
import unittest
from decimal import Decimal

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p2_pb2 as p2
from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p3 import audit, _rate


def q(x, unit=b.T4_MILLIMETER, source='input'):
    return b.T4Quantity(value=x,unit=unit,
        evidence=b.T4_MEASUREMENT_ASSERTED,source_ref=source)


def iv(x, radius=0, unit=b.T4_MILLIMETER):
    z=p2.T4P2Interval()
    z.center.CopyFrom(q(x,unit))
    z.radius.CopyFrom(q(radius,unit))
    return z


def case(root, key, *, split=p3.T4P3_HOLDOUT, bore=10.2, shaft=10.0,
         radius=.01, observed=p3.T4P3_OBSERVED_SATISFIES,
         numeric=None, ref_source='external', kind=p3.T4P3_SYNTHETIC_ORACLE):
    c=root.cases.add(case_id=key, specimen_group_id='specimen_'+key,
         reference_source_ref=ref_source,
         reference_sha256=hashlib.sha256(('REFERENCE:'+key).encode()).digest(),
         partition=split, reference_kind=kind,observed_class=observed,finding_id='fit')
    if numeric is not None:
        c.observed_clearance_m = numeric
    r=c.scenario
    r.schema_version=1
    r.research_only=True
    r.baseline.schema_version=1
    r.baseline.graph_id='graph_'+key
    r.baseline.conversation_id=root.conversation_id
    r.baseline.research_only=True
    for id in ('bore','shaft'):
        r.baseline.parts.add(id=id,kind='physical_part',
            source_ref='part_input',evidence=b.T4_MEASUREMENT_ASSERTED)
    f=r.fits.add(id='fit',bore_part_id='bore',shaft_part_id='shaft')
    f.bore_diameter.CopyFrom(iv(bore,radius))
    f.shaft_diameter.CopyFrom(iv(shaft,radius))
    f.allowed_min_clearance.CopyFrom(iv(.1,0))
    f.allowed_max_clearance.CopyFrom(iv(.3,0))
    return c


def request():
    return p3.T4P3AuditRequest(schema_version=1,study_id='t4_p3_test',
        conversation_id='convo_demo',research_only=True,
        prespecified_plan_sha256=hashlib.sha256(b'locked-pretend-plan').digest())


class T4P3Tests(unittest.TestCase):
    def denied(self, x, code):
        with self.assertRaisesRegex(T4Rejected,code): audit(x)

    def test_simple_synthetic_holdout(self):
        r=request()
        case(r,'pass',numeric=.0002)
        case(r,'fail',shaft=10.5,observed=p3.T4P3_OBSERVED_VIOLATES,numeric=-.0003)
        o=audit(r)
        self.assertEqual(o.holdout.cases,2)
        self.assertEqual(o.holdout.decided,2)
        self.assertEqual(o.holdout.false_positive,0)
        self.assertEqual(o.holdout.false_negative,0)
        self.assertEqual(o.holdout.claimed_interval_coverage.numerator,2)
        self.assertEqual(o.holdout.claimed_interval_coverage.denominator,2)
        self.assertTrue(o.holdout.selective_error.defined)
        self.assertFalse(o.physical_validity_verified)
        self.assertFalse(o.independent_evidence_authenticated)
        self.assertFalse(o.grants_authority)
        self.assertEqual(len(o.request_sha256),32)

    def test_class_falsification_false_positive(self):
        r=request()
        case(r,'fp',observed=p3.T4P3_OBSERVED_VIOLATES,numeric=.00035)
        out=audit(r)
        self.assertEqual(out.holdout.false_positive,1)
        self.assertEqual(out.holdout.false_positive_rate.estimate,1)
        self.assertTrue(out.audited_cases[0].label_falsifies_decision)
        self.assertTrue(out.audited_cases[0].claimed_interval_falsified)

    def test_class_falsification_false_negative(self):
        r=request()
        case(r,'fn',shaft=10.5,numeric=.0002)
        o=audit(r)
        self.assertEqual(o.holdout.false_negative,1)
        self.assertEqual(o.holdout.false_negative_rate.estimate,1)
        self.assertTrue(o.audited_cases[0].label_falsifies_decision)

    def test_abstention_counted_not_dropped(self):
        r=request()
        case(r,'amb',shaft=10.1,radius=.05,numeric=.0001)
        o=audit(r)
        self.assertEqual(o.holdout.abstained,1)
        self.assertFalse(o.holdout.selective_error.defined)
        self.assertEqual(o.holdout.decision_coverage.estimate,0)

    def test_unknown_reference_label_not_counted_as_truth(self):
        r=request()
        case(r,'unknown',observed=p3.T4P3_OBSERVED_UNDETERMINED)
        o=audit(r)
        self.assertEqual(o.holdout.reference_unknown,1)
        self.assertEqual(o.holdout.decided,0)
        self.assertFalse(o.holdout.decision_coverage.defined)
        self.assertIn('REFERENCE_CLASS_UNDETERMINED',o.audited_cases[0].reason_codes)

    def test_numeric_zero_is_present_not_missing(self):
        r=request()
        case(r,'zero',numeric=0)
        o=audit(r)
        self.assertTrue(o.audited_cases[0].numeric_reference_available)
        self.assertTrue(o.audited_cases[0].claimed_interval_falsified)

    def test_numeric_nan_rejected(self):
        r=request();case(r,'nan',numeric=float('nan'))
        self.denied(r,'NONFINITE_REFERENCE_OBSERVATION')

    def test_numeric_inf_rejected(self):
        r=request();case(r,'inf',numeric=float('inf'))
        self.denied(r,'NONFINITE_REFERENCE_OBSERVATION')

    def test_requires_explicit_research_mode(self):
        r=request();case(r,'x');r.grants_authority=True
        self.denied(r,'INVALID_P3_CONTRACT')

    def test_missing_plan_fails_closed(self):
        r=request();case(r,'x');r.prespecified_plan_sha256=b''
        self.denied(r,'MISSING_PLAN_IDENTITY')

    def test_digest_is_identifier_only(self):
        r=request();case(r,'x')
        o=audit(r)
        self.assertIn('REFERENCE_SOURCE_AND_SHA256_UNAUTHENTICATED',o.warnings)

    def test_unknown_source_is_invalid(self):
        r=request();case(r,'x');r.cases[0].reference_kind=p3.T4P3_REFERENCE_UNSPECIFIED
        self.denied(r,'UNKNOWN_REFERENCE_PROVENANCE')

    def test_unknown_label_is_invalid(self):
        r=request();case(r,'x');r.cases[0].observed_class=p3.T4P3_OBSERVED_UNSPECIFIED
        self.denied(r,'UNKNOWN_REFERENCE_CLASS')

    def test_unknown_partition_is_invalid(self):
        r=request();case(r,'x');r.cases[0].partition=p3.T4P3_PARTITION_UNSPECIFIED
        self.denied(r,'UNKNOWN_EVALUATION_PARTITION')

    def test_reused_input_source_is_rejected(self):
        r=request();case(r,'x',ref_source='input')
        self.denied(r,'REFERENCE_REUSED_AS_MODEL_INPUT')

    def test_reused_part_source_is_rejected(self):
        r=request();case(r,'x',ref_source='part_input')
        self.denied(r,'REFERENCE_REUSED_AS_MODEL_INPUT')

    def test_cross_conversation_case_rejected(self):
        r=request();case(r,'x');r.cases[0].scenario.baseline.conversation_id='other'
        self.denied(r,'CROSS_CONVERSATION_EVIDENCE')

    def test_duplicate_case_id_rejected(self):
        r=request();case(r,'x');case(r,'x')
        self.denied(r,'DUPLICATE_CASE_ID')

    def test_correlated_specimen_rejected(self):
        r=request();case(r,'x');case(r,'y')
        r.cases[1].specimen_group_id='specimen_x'
        self.denied(r,'DEPENDENT_OR_DUPLICATE_SPECIMEN')

    def test_cross_partition_leak_rejected(self):
        r=request();case(r,'x',split=p3.T4P3_CALIBRATION)
        z=case(r,'y')
        z.scenario.CopyFrom(r.cases[0].scenario)
        self.denied(r,'CALIBRATION_HOLDOUT_SCENARIO_LEAK')

    def test_missing_p2_finding_rejected(self):
        r=request();c=case(r,'x');c.finding_id='not_found'
        self.denied(r,'MISSING_OR_DUPLICATE_P2_FINDING')

    def test_empty_partitions_are_explicit_not_pass(self):
        r=request();case(r,'only_cal',split=p3.T4P3_CALIBRATION)
        o=audit(r)
        self.assertFalse(o.holdout.selective_error.defined)
        self.assertEqual(o.holdout.cases,0)
        self.assertFalse(o.holdout.claimed_interval_coverage.defined)

    def test_nominal_coverage_is_not_inferred(self):
        r=request();case(r,'x',numeric=.0002)
        o=audit(r)
        self.assertEqual(o.holdout.nominal_coverage_audit,'NO_PROBABILITY_COVERAGE_CLAIM')

    def test_nominal_requires_sample_and_claim(self):
        r=request();case(r,'x',numeric=.0002);r.claimed_nominal_coverage=.9
        o=audit(r)
        self.assertEqual(o.holdout.nominal_coverage_audit,'INSUFFICIENT_NUMERIC_SAMPLE')
        r.claimed_nominal_coverage=1.0
        self.denied(r,'INVALID_NOMINAL_COVERAGE_CLAIM')

    def test_wilson_known_reference(self):
        z=_rate(0,10)
        self.assertTrue(z.defined)
        self.assertAlmostEqual(z.wilson_95_high, .2775327998628892,places=10)
        w=_rate(5,10)
        self.assertAlmostEqual(w.wilson_95_low, .23659309051256394,places=10)
        self.assertAlmostEqual(w.wilson_95_high,.763406909487436,places=10)
        self.assertFalse(_rate(0,0).defined)

    def test_literature_claim_not_authenticated(self):
        r=request();case(r,'x',kind=p3.T4P3_PUBLISHED_REFERENCE_CLAIM)
        o=audit(r)
        self.assertTrue(o.holdout.contains_non_synthetic_claims)
        self.assertFalse(o.independent_evidence_authenticated)

    def test_roundtrip_stable_sha(self):
        r=request();case(r,'a');case(r,'b')
        raw=r.SerializeToString(deterministic=True)
        d=p3.T4P3AuditRequest.FromString(raw)
        self.assertEqual(audit(r).SerializeToString(deterministic=True),
                         audit(d).SerializeToString(deterministic=True))

    def test_canonical_sorting_case_order(self):
        r=request();case(r,'z');case(r,'a')
        o=audit(r)
        self.assertEqual([x.case_id for x in o.audited_cases],['a','z'])

    def test_mixed_synthetic_audit_rates(self):
        r=request()
        for i in range(60):
            split=p3.T4P3_CALIBRATION if i < 30 else p3.T4P3_HOLDOUT
            if i%3==0:
                case(r,f'x{i}',split=split,numeric=.0002)
            elif i%3==1:
                case(r,f'x{i}',split=split,shaft=10.5,
                    observed=p3.T4P3_OBSERVED_VIOLATES,numeric=-.0003)
            else:
                case(r,f'x{i}',split=split,observed=p3.T4P3_OBSERVED_VIOLATES,numeric=.00035)
        o=audit(r)
        self.assertEqual(o.calibration.cases,30)
        self.assertEqual(o.holdout.cases,30)
        self.assertEqual(o.holdout.false_positive,10)
        self.assertAlmostEqual(o.holdout.false_positive_rate.estimate,.5)
        self.assertEqual(o.holdout.claimed_interval_coverage.numerator,20)
        self.assertTrue(o.holdout.has_enough_cases_for_exploratory_rates)

    def test_incorrect_measured_label_is_still_unverified(self):
        # Never claim labels are authenticated merely because a value was given.
        r=request();case(r,'dishonest',numeric=.0002,observed=p3.T4P3_OBSERVED_VIOLATES)
        o=audit(r)
        self.assertTrue(o.audited_cases[0].label_falsifies_decision)
        self.assertFalse(o.independent_evidence_authenticated)

    def test_real_scope_no_llm_or_worker_control(self):
        r=request();case(r,'x')
        self.assertFalse(audit(r).grants_authority)
        self.assertTrue(audit(r).research_only)

    def test_load_classification_without_numeric_fit_promotion(self):
        r=request()
        c=case(r,'loadcase')
        c.finding_id='load'
        c.scenario.ClearField('fits')
        c.scenario.baseline.parts.add(id='beam',kind='beam',evidence=b.T4_MEASUREMENT_ASSERTED,
            source_ref='part_input')
        x=c.scenario.loads.add(id='load',part_id='beam',safety_factor=1.5)
        x.axial_area.CopyFrom(iv(100,0,b.T4_SQUARE_MILLIMETER))
        x.shear_area.CopyFrom(iv(80,0,b.T4_SQUARE_MILLIMETER))
        x.section_modulus.CopyFrom(p2.T4P2SIInterval(center_si=1e-6,
            evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='input'))
        x.allowable_normal_stress.CopyFrom(iv(200,0,b.T4_MEGAPASCAL))
        x.allowable_shear_stress.CopyFrom(iv(100,0,b.T4_MEGAPASCAL))
        z=x.cases.add(id='steady')
        z.axial_force.CopyFrom(iv(1000,0,b.T4_NEWTON))
        z.shear_force.CopyFrom(iv(100,0,b.T4_NEWTON))
        z.bending_moment.CopyFrom(p2.T4P2SIInterval(center_si=5,
            evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='input'))
        o=audit(r)
        self.assertEqual(o.holdout.decided,1)
        self.assertFalse(o.holdout.claimed_interval_coverage.defined)
        c.observed_clearance_m=.2
        self.denied(r,'NUMERIC_REFERENCE_WRONG_DIMENSION')

    def test_all_reference_hashes_identity_only(self):
        r=request();case(r,'fake')
        r.cases[0].reference_sha256=b'\x00'*32
        self.assertFalse(audit(r).independent_evidence_authenticated)

    def test_case_count_resource_limit(self):
        r=request()
        for i in range(161):
            case(r,f'c{i}')
        self.denied(r,'P3_RESOURCE_LIMIT')

    def test_unspecified_nominal_not_automatic_coverage(self):
        r=request();case(r,'foo',numeric=.0002)
        self.assertEqual(audit(r).holdout.nominal_coverage_audit,
                         'NO_PROBABILITY_COVERAGE_CLAIM')

    def test_invalid_p2_baseline_still_denied(self):
        r=request();case(r,'x');r.cases[0].scenario.baseline.parts[0].id='unknown/invalid'
        self.denied(r,'INVALID_PART')


if __name__=='__main__':
    unittest.main()
