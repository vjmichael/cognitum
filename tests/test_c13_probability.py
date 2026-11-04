"""C13 Bayesian inference correctness and failure-status regression."""
import math
import unittest
from dataclasses import replace
from cognitum.probability_bayes import BayesProblem, Observation, validate, infer
from cognitum.probability_calibration import (
    BetaProblem,CalibrationProblem,beta_posterior,calibration_scores,
)


def disease():
    return BayesProblem(
        ("disease","healthy"),(0.01,0.99),
        (Observation("test_positive",(0.9,0.05)),),
        "population_study","diagnostic_study",
        ("conditionally_independent_observations",),
    )


class C13BayesianTests(unittest.TestCase):
    def test_base_rate_inversion_and_normalization(self):
        result=infer(disease())
        self.assertEqual(result.status,"OK")
        truth=0.009/(0.009+0.0495)
        self.assertAlmostEqual(result.posterior[0],truth,places=12)
        self.assertAlmostEqual(sum(result.posterior),1.0,places=12)
        self.assertAlmostEqual(result.evidence_probability,0.0585,places=12)
        self.assertIn("association_not_causation",result.limitations)

    def test_negative_evidence_and_logspace_underflow(self):
        p=replace(disease(),observations=(Observation("test_negative",(0.9,0.05),False),))
        result=infer(p)
        self.assertEqual(result.status,"OK")
        self.assertAlmostEqual(result.posterior[0],0.001/(0.001+0.9405),places=12)
        # 32 independent tiny likelihoods would underflow naive products.
        many=replace(disease(),observations=tuple(
            Observation("e"+str(i),(1e-60,2e-60)) for i in range(32)))
        stable=infer(many)
        self.assertEqual(stable.status,"OK")
        self.assertAlmostEqual(sum(stable.posterior),1.0,places=12)
        self.assertTrue(math.isfinite(stable.log_evidence))

    def test_impossible_evidence_is_not_fabricated_posterior(self):
        p=replace(disease(),observations=(Observation("contradiction",(0,0)),))
        result=infer(p)
        self.assertEqual(result.status,"IMPOSSIBLE_EVIDENCE")
        self.assertEqual(result.posterior,())

    def test_double_count_and_assumption_refusal(self):
        p=disease()
        for invalid in (
            replace(p,observations=p.observations+p.observations),
            replace(p,assumptions=()),
            replace(p,assumptions=("unconditional_independence",)),
            replace(p,prior_source=""),
            replace(p,prior=(0.5,0.6)),
            replace(p,prior=(-0.01,1.01)),
            replace(p,prior=(True,0.99)),
            replace(p,observations=(Observation("e",(0.5,float("nan"))),)),
            replace(p,observations=(Observation("e",(0.5,0.2),True),)*33),
        ):
            with self.subTest(case=repr(invalid)[:90]),self.assertRaises(ValueError):
                validate(invalid)

    def test_beta_binomial_reference(self):
        p=BetaProblem(8,2,1,1,0.95,"prior_registry","heldout_trials")
        result=beta_posterior(p)
        self.assertEqual(result.status,"OK")
        self.assertAlmostEqual(result.posterior_mean,0.75)
        self.assertLess(result.credible_lower,result.posterior_mean)
        self.assertLess(result.posterior_mean,result.credible_upper)
        self.assertIn("credible_interval_not_frequentist_confidence",result.limitations)
        with self.assertRaises(ValueError):
            beta_posterior(replace(p,credibility=1.0))

    def test_calibration_scorers_with_observed_truth(self):
        c=CalibrationProblem((1.0,)*5+(0.0,)*5,(1,)*5+(0,)*5,"heldout_case")
        result=calibration_scores(c)
        self.assertAlmostEqual(result.brier,0.0)
        self.assertLess(result.log_loss,1e-10)
        self.assertAlmostEqual(result.expected_calibration_error,0.0)
        mixed=calibration_scores(CalibrationProblem((0.5,)*10,(0,1)*5,"holdout"))
        self.assertAlmostEqual(mixed.brier,0.25)
        self.assertAlmostEqual(mixed.log_loss,math.log(2))
        self.assertAlmostEqual(mixed.expected_calibration_error,0.0)

    def test_calibration_requires_real_labels_and_sample(self):
        base=CalibrationProblem((0.4,)*10,(0,1)*5,"holdout")
        for bad in (
            replace(base,labels=(0,)*9),
            replace(base,probabilities=(float("nan"),)*10),
            replace(base,labels=(True,)*10),
            replace(base,source=""),
            replace(base,bins=21),
            replace(base,labels=(0,)*9+(2,)),
            replace(base,probabilities=(1.1,)*10),
        ):
            with self.subTest(bad=repr(bad)[:80]),self.assertRaises(ValueError):
                calibration_scores(bad)


if __name__=="__main__":
    unittest.main()
