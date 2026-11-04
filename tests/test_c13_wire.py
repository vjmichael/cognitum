"""C13 native statistical wire: real SciPy, canonical and forged-result tests."""
from hashlib import sha256
import math
import unittest
from cognitum.proto import probability_pb2 as pb
from cognitum.probability_wire import execute,decode_result


def bayes_case():
    req=pb.BayesRequest(schema_version=1,hypotheses=["ill","well"],
        prior=[0.01,0.99],prior_source="population_study",
        likelihood_source="test_study",
        assumptions=["conditionally_independent_observations"])
    req.observations.add(name="positive_test",
        likelihood_by_hypothesis=[0.9,0.05],observed=True)
    return req.SerializeToString(deterministic=True)


def beta_case():
    return pb.BetaRequest(schema_version=1,successes=8,failures=2,
        alpha_prior=1,beta_prior=1,credibility=0.95,
        prior_source="registry",data_source="trials").SerializeToString(deterministic=True)


def calibration_case():
    return pb.CalibrationRequest(schema_version=1,source="test_holdout",bins=10,
        probabilities=[1.0]*5+[0.0]*5,
        labels=[1]*5+[0]*5).SerializeToString(deterministic=True)


class C13WireTests(unittest.TestCase):
    def test_native_bayesian_updates_and_provenance(self):
        result=decode_result("bayes",bayes_case(),execute("bayes",bayes_case()))
        self.assertEqual(result.status,"OK")
        self.assertAlmostEqual(result.posterior[0],0.009/0.0585,places=12)
        self.assertEqual(result.request_sha256,sha256(bayes_case()).hexdigest())
        self.assertIn("not_empirically_calibrated",result.limitations)

    def test_native_beta_and_calibration(self):
        beta=decode_result("beta",beta_case(),execute("beta",beta_case()))
        self.assertEqual(beta.status,"OK")
        self.assertAlmostEqual(beta.posterior_mean,0.75)
        cal=decode_result("calibration",calibration_case(),
                          execute("calibration",calibration_case()))
        self.assertEqual(cal.status,"OK")
        self.assertEqual(cal.count,10)
        self.assertAlmostEqual(cal.brier,0.0)
        self.assertAlmostEqual(cal.expected_calibration_error,0.0)

    def test_unknown_and_noncanonical_wire_rejection(self):
        raw=bayes_case()
        for invalid in (b"",raw+b"\x98\x06\x01",raw+b"\x08\x01",
                        b"\x0a\xff",b"z"*(1024*1024+1)):
            with self.subTest(raw=invalid[:10]),self.assertRaises(ValueError):
                execute("bayes",invalid)
        with self.assertRaises(ValueError):
            execute("code",raw)

    def test_wrong_hypothesis_and_source_rejected(self):
        req=pb.BayesRequest()
        req.ParseFromString(bayes_case())
        req.prior_source=""
        with self.assertRaises(ValueError):
            execute("bayes",req.SerializeToString(deterministic=True))
        req.ParseFromString(bayes_case())
        req.observations[0].likelihood_by_hypothesis[0]=float("nan")
        with self.assertRaises(ValueError):
            execute("bayes",req.SerializeToString(deterministic=True))

    def test_forged_posterior_rejected(self):
        request=bayes_case()
        response=pb.BayesResult()
        response.ParseFromString(execute("bayes",request))
        response.posterior[0]=0.8
        response.posterior[1]=0.2
        with self.assertRaises(ValueError):
            decode_result("bayes",request,
                          response.SerializeToString(deterministic=True))

    def test_no_model_executable_payload(self):
        for cls in (pb.BayesRequest,pb.BetaRequest,pb.CalibrationRequest):
            fields={f.name for f in cls.DESCRIPTOR.fields}
            for name in ("code","python","script","shell","host_grants"):
                self.assertNotIn(name,fields)


if __name__=="__main__":
    unittest.main()
