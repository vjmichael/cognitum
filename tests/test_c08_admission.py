"""C08 must not enable HDC solely because it exists."""
import unittest
from cognitum.research.hdc_admission import (
    Admission, RetrievalMeasurements, choose_retrieval,
)


def receipt(**changes):
    base = dict(dataset_id="heldout-1", trials=80, exact_recall=0.98,
                hdc_recall=0.99, exact_median_ms=6.0, hdc_median_ms=3.0,
                verified_false_positives=0, independent_host_measurement=True)
    base.update(changes)
    return RetrievalMeasurements(**base)


class HdcAdmissionTests(unittest.TestCase):
    def decision(self, **kwargs):
        base = dict(user_opted_in=True, host_approved=True,
                    independent_measurements=receipt())
        base.update(kwargs)
        return choose_retrieval(**base)

    def test_default_off(self):
        self.assertEqual(self.decision(user_opted_in=False).route, "exact_or_fts5")

    def test_host_denial(self):
        self.assertFalse(self.decision(host_approved=False).enabled)

    def test_unmeasured_not_enabled(self):
        self.assertFalse(self.decision(independent_measurements=None).enabled)
        self.assertFalse(self.decision(
            independent_measurements=receipt(independent_host_measurement=False)
        ).enabled)

    def test_no_quality_regression(self):
        self.assertFalse(self.decision(
            independent_measurements=receipt(hdc_recall=0.97)
        ).enabled)
        self.assertFalse(self.decision(
            independent_measurements=receipt(verified_false_positives=1)
        ).enabled)

    def test_no_latency_regression(self):
        self.assertFalse(self.decision(
            independent_measurements=receipt(hdc_median_ms=5.5)
        ).enabled)

    def test_opt_in_and_measured_speedup_admit_only_candidate_route(self):
        result = self.decision()
        self.assertTrue(result.enabled)
        self.assertEqual(result.route, "hdc_candidates_with_canonical_recheck")

    def test_invalid_benchmark_refused(self):
        with self.assertRaises(ValueError):
            receipt(trials=2)
        with self.assertRaises(ValueError):
            receipt(hdc_median_ms=float("nan"))
        with self.assertRaises(ValueError):
            self.decision(min_speedup=0.1)


if __name__ == "__main__":
    unittest.main()
