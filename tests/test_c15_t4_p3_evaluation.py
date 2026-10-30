"""Frozen synthetic P3 evaluation fixture; not physical holdout verification."""
import importlib.util
from pathlib import Path
import unittest
from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.spatial_functional_material_p3 import audit

MODULE=Path(__file__).resolve().parents[1]/'evals'/'c15_t4_p3_synthetic_heldout.py'
spec=importlib.util.spec_from_file_location('c15_t4_p3_synthetic_heldout',MODULE)
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class T4P3SyntheticStudy(unittest.TestCase):
    def test_segregated_specimens_and_counts(self):
        req=mod.study()
        self.assertEqual(len(req.cases),80)
        self.assertEqual(len({c.specimen_group_id for c in req.cases}),80)
        self.assertEqual(sum(c.partition==p3.T4P3_CALIBRATION for c in req.cases),40)
        self.assertEqual(sum(c.partition==p3.T4P3_HOLDOUT for c in req.cases),40)
        self.assertTrue(all(c.reference_kind==p3.T4P3_SYNTHETIC_ORACLE for c in req.cases))

    def test_heldout_intentional_falsification_regression(self):
        x=audit(mod.study())
        self.assertEqual((x.calibration.decided,x.calibration.abstained),(35,5))
        self.assertEqual((x.holdout.decided,x.holdout.abstained),(35,5))
        self.assertEqual((x.calibration.false_positive,x.calibration.false_negative),(5,0))
        self.assertEqual((x.holdout.false_positive,x.holdout.false_negative),(10,5))
        self.assertEqual(x.holdout.claimed_interval_coverage.numerator,25)
        self.assertEqual(x.holdout.claimed_interval_coverage.denominator,40)
        self.assertEqual(x.holdout.nominal_coverage_audit,'EMPIRICAL_COVERAGE_BELOW_CLAIM')
        self.assertFalse(x.physical_validity_verified)

    def test_nominal_claim_is_not_calibration(self):
        r=mod.study()
        with_nominal=audit(r)
        r.claimed_nominal_coverage=0
        without_nominal=audit(r)
        self.assertEqual(with_nominal.holdout.claimed_interval_coverage.numerator,
                         without_nominal.holdout.claimed_interval_coverage.numerator)
        self.assertEqual(without_nominal.holdout.nominal_coverage_audit,
                         'NO_PROBABILITY_COVERAGE_CLAIM')

    def test_report_admits_no_real_measurement(self):
        report=mod.output()
        self.assertEqual(report['source'],'synthetic_decimal_oracle_only')
        self.assertFalse(report['physically_verified'])
        self.assertFalse(report['independent_evidence_authenticated'])
        self.assertFalse(report['reference_runtime_only']['energy_measured'])
        self.assertEqual(len(report['falsifications']),15)

if __name__=='__main__': unittest.main()
