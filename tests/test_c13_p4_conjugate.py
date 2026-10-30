"""C13 P4 analytic Bayesian family functionality, request-bound numerical audits."""
import hashlib
import math
import random
import unittest
from scipy import stats
from cognitum import probability_conjugate as c
from cognitum.proto import probability_conjugate_pb2 as p


def make(kind='beta_binomial'):
    req=p.ConjugateRequest(schema_version=1,trace_id='c13.p4',timeout_ms=10000)
    if kind=='beta_binomial':
        m=req.beta_binomial;m.prior_alpha=2;m.prior_beta=3;m.successes=8;m.failures=4;m.future_trials=12
    elif kind=='gamma_poisson':
        m=req.gamma_poisson;m.prior_shape=3;m.prior_rate=2;m.future_exposure=2
        m.observations.add(count=4,exposure=2)
        m.observations.add(count=2,exposure=1)
    elif kind=='normal_inverse_gamma':
        m=req.normal_inverse_gamma;m.prior_mu=1;m.prior_kappa=2;m.prior_alpha=3;m.prior_beta=2
        m.observations.extend([3.,4.,5.,2.])
    else:raise ValueError(kind)
    return req


def run(req=None,authorized=True,enabled=True):
    req=req or make();raw=req.SerializeToString(deterministic=True)
    frame=c.run_conjugate_frame(raw,host_authorized=authorized,enabled=enabled)
    return raw,frame,p.ConjugateResult.FromString(frame)

class ConjugateTests(unittest.TestCase):
    def test_beta_binomial_posterior(self):
        raw,frame,r=run()
        self.assertEqual(r.status,p.CONJUGATE_SUCCESS)
        self.assertAlmostEqual(r.shape_a,10)
        self.assertAlmostEqual(r.shape_b,7)
        self.assertAlmostEqual(r.posterior_mean,10/17)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
        self.assertEqual(r.predictive_lower_95,int(r.predictive_lower_95))
        self.assertLessEqual(r.predictive_lower_95,r.predictive_upper_95)
    def test_gamma_poisson_rate_and_predictive(self):
        raw,frame,r=run(make('gamma_poisson'))
        self.assertAlmostEqual(r.shape_a,9)
        self.assertAlmostEqual(r.shape_b,5)
        self.assertAlmostEqual(r.predictive_mean,18/5)
        self.assertGreater(r.predictive_variance,r.predictive_mean)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_normal_inverse_gamma_unknown_variance(self):
        raw,frame,r=run(make('normal_inverse_gamma'))
        self.assertAlmostEqual(r.shape_a,5.)
        self.assertAlmostEqual(r.strength,6.)
        self.assertTrue(r.posterior_variance_defined)
        self.assertGreater(r.predictive_variance,r.posterior_variance)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_no_data_prior(self):
        for kind in ('beta_binomial','gamma_poisson','normal_inverse_gamma'):
            req=make(kind)
            if kind=='beta_binomial':req.beta_binomial.successes=0;req.beta_binomial.failures=0
            elif kind=='gamma_poisson':req.gamma_poisson.ClearField('observations')
            else:req.normal_inverse_gamma.ClearField('observations')
            raw,frame,r=run(req);self.assertEqual(r.status,p.CONJUGATE_SUCCESS,kind)
            self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_undefined_student_t_moments_explicit(self):
        req=make('normal_inverse_gamma')
        m=req.normal_inverse_gamma;m.ClearField('observations');m.prior_alpha=.25
        raw,frame,r=run(req)
        self.assertEqual(r.status,p.CONJUGATE_SUCCESS)
        self.assertFalse(r.posterior_mean_defined)
        self.assertFalse(r.posterior_variance_defined)
        self.assertFalse(r.predictive_mean_defined)
        self.assertFalse(r.predictive_variance_defined)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_student_t_mean_without_variance(self):
        req=make('normal_inverse_gamma');req.normal_inverse_gamma.ClearField('observations')
        req.normal_inverse_gamma.prior_alpha=.75
        raw,frame,r=run(req)
        self.assertTrue(r.posterior_mean_defined)
        self.assertFalse(r.posterior_variance_defined)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_zero_future_trials_point_mass(self):
        req=make();req.beta_binomial.future_trials=0
        raw,frame,r=run(req)
        self.assertEqual(r.predictive_mean,0)
        self.assertEqual(r.predictive_variance,0)
        self.assertEqual(r.predictive_lower_95,0)
        self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_reproducibility_seed_free_analytic(self):
        req=make('gamma_poisson');a=run(req)[1];b=run(req)[1]
        aa=p.ConjugateResult.FromString(a);bb=p.ConjugateResult.FromString(b)
        aa.wall_ns=bb.wall_ns=0
        self.assertEqual(aa,bb)
    def test_random_small_models(self):
        rng=random.Random(1394)
        for _ in range(45):
            kind=rng.choice(('beta_binomial','gamma_poisson','normal_inverse_gamma'))
            req=make(kind)
            if kind=='beta_binomial':
                m=req.beta_binomial;m.prior_alpha=rng.uniform(.1,15);m.prior_beta=rng.uniform(.1,15)
                m.successes=rng.randrange(30);m.failures=rng.randrange(30);m.future_trials=rng.randrange(35)
            elif kind=='gamma_poisson':
                m=req.gamma_poisson;m.prior_shape=rng.uniform(.1,15);m.prior_rate=rng.uniform(.1,15);m.future_exposure=rng.uniform(.1,10)
                m.ClearField('observations')
                for _ in range(rng.randrange(7)):m.observations.add(count=rng.randrange(20),exposure=rng.uniform(.1,5))
            else:
                m=req.normal_inverse_gamma;m.prior_mu=rng.uniform(-10,10);m.prior_kappa=rng.uniform(.1,10)
                m.prior_alpha=rng.uniform(.1,10);m.prior_beta=rng.uniform(.1,10)
                m.ClearField('observations');m.observations.extend(rng.uniform(-10,10) for _ in range(rng.randrange(12)))
            raw,frame,r=run(req)
            self.assertEqual(r.status,p.CONJUGATE_SUCCESS,(kind,r.reason_code))
            self.assertTrue(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_independent_beta_binomial_predictive_pmf_normalization(self):
        req=make();raw,frame,r=run(req)
        a=r.shape_a;b=r.shape_b;n=req.beta_binomial.future_trials
        self.assertAlmostEqual(sum(stats.betabinom.pmf(k,n,a,b) for k in range(n+1)),1.0,places=9)
    def test_gamma_poisson_negative_binomial_mean_identity(self):
        req=make('gamma_poisson');r=run(req)[2]
        self.assertAlmostEqual(stats.nbinom.mean(r.shape_a,r.shape_b/(r.shape_b+req.gamma_poisson.future_exposure)),r.predictive_mean)
    def test_nig_student_t_quantile_matches_cdf(self):
        r=run(make('normal_inverse_gamma'))[2]
        scale=math.sqrt(r.shape_b/(r.shape_a*r.strength))
        self.assertAlmostEqual(stats.t.cdf(r.credible_lower_95,2*r.shape_a,loc=r.location,scale=scale),.025,places=8)

    def test_wrong_schema(self):
        req=make();req.schema_version=3
        self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_malformed_frame(self):
        r=p.ConjugateResult.FromString(c.run_conjugate_frame(b'\xff',host_authorized=True,enabled=True))
        self.assertEqual(r.status,p.CONJUGATE_REJECTED)
    def test_oversized_frame(self):
        r=p.ConjugateResult.FromString(c.run_conjugate_frame(b'x'*70000,host_authorized=True,enabled=True))
        self.assertEqual(r.status,p.CONJUGATE_REJECTED)
    def test_missing_family(self):
        req=make();req.ClearField('beta_binomial');self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_authorization(self):
        self.assertEqual(run(authorized=False)[2].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled(self):
        self.assertEqual(run(enabled=False)[2].reason_code,'PROBABILITY_DISABLED')
    def test_bad_trace(self):
        req=make();req.trace_id='???';self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_bad_timeout(self):
        req=make();req.timeout_ms=0;self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_nonfinite_priors(self):
        for kind in ('beta_binomial','gamma_poisson','normal_inverse_gamma'):
            req=make(kind)
            if kind=='beta_binomial':req.beta_binomial.prior_alpha=float('nan')
            elif kind=='gamma_poisson':req.gamma_poisson.prior_rate=float('inf')
            else:req.normal_inverse_gamma.prior_alpha=float('nan')
            self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_nonfinite_observation(self):
        req=make('normal_inverse_gamma');req.normal_inverse_gamma.observations.append(float('inf'))
        self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_invalid_exposure(self):
        req=make('gamma_poisson');req.gamma_poisson.observations[0].exposure=0
        self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_excessive_counts(self):
        req=make('gamma_poisson');req.gamma_poisson.observations[0].count=100001
        self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_observations_budget(self):
        req=make('normal_inverse_gamma');req.normal_inverse_gamma.observations.extend([1.] * 129)
        self.assertEqual(run(req)[2].status,p.CONJUGATE_REJECTED)
    def test_no_generated_executable_path(self):
        self.assertNotIn('executable',[field.name for field in p.ConjugateRequest.DESCRIPTOR.fields])
    def test_tampered_mean(self):
        raw,frame,r=run();r.posterior_mean+=.1
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_tampered_credible_interval(self):
        raw,frame,r=run(make('normal_inverse_gamma'));r.credible_lower_95+=.1
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_tampered_predictive(self):
        raw,frame,r=run(make('gamma_poisson'));r.predictive_variance+=.1
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_forged_success(self):
        raw,frame,r=run();r.independently_recomputed=False
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_wrong_request_digest(self):
        raw,frame,r=run();r.request_sha256=b'?'*32
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_wrong_family(self):
        raw,frame,r=run();r.model_family='gamma_poisson'
        self.assertFalse(c.verify_conjugate_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_fail_closed_unknown_receipt(self):
        raw,frame,r=run(authorized=False)
        self.assertFalse(c.verify_conjugate_receipt(raw,frame).evidence_valid)
    def test_reject_forged_receipt(self):
        raw,frame,r=run();receipt=c.verify_conjugate_receipt(raw,frame);receipt.evidence_valid=False
        with self.assertRaisesRegex(ValueError,'FORGED_RECEIPT'):c.make_conjugate_audit(raw,frame,receipt)
    def test_privacy_minimized_audit(self):
        raw,frame,r=run()
        audit=c.make_conjugate_audit(raw,frame)
        self.assertTrue(audit.independently_recomputed)
        self.assertEqual(audit.request_sha256,hashlib.sha256(raw).digest())
        self.assertEqual(audit.result_sha256,hashlib.sha256(frame).digest())
        self.assertNotIn(b'future_trials',audit.SerializeToString())
    def test_model_family_only_from_typed_oneof(self):
        req=make('normal_inverse_gamma')
        self.assertEqual(req.WhichOneof('model'),'normal_inverse_gamma')
        req.beta_binomial.prior_alpha=5
        self.assertEqual(req.WhichOneof('model'),'beta_binomial')

if __name__=='__main__':unittest.main()
