"""Focused mathematical and worker-boundary tests; not model benchmarks."""
import hashlib
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from cognitum import probability_continuous as c
from cognitum.proto import probability_continuous_pb2 as p


def request(backend=p.GAUSSIAN_CONJUGATE_REFERENCE):
    r=p.ContinuousRequest(schema_version=1,trace_id='c13.p3',backend=backend,timeout_ms=10000)
    m=r.model
    m.group_ids.extend(('urban','rural'))
    m.global_prior_mean=0.0
    m.global_prior_sd=2.0
    m.group_sd=1.0
    m.predictive_sd=1.5
    m.observations.add(group=0,value=2.0,known_sd=1.0)
    m.observations.add(group=0,value=3.0,known_sd=2.0)
    if backend!=p.GAUSSIAN_CONJUGATE_REFERENCE:
        r.draws=50;r.warmup=20;r.chains=2;r.seed=9
    return r


def execute(req=None,*,authorized=True,enabled=True,policy=None):
    req=req or request()
    raw=req.SerializeToString(deterministic=True)
    result=c.run_continuous_frame(raw,host_authorized=authorized,enabled=enabled,worker_policy=policy)
    return raw,result,p.ContinuousResult.FromString(result)

class ContinuousTests(unittest.TestCase):
    def test_exact_hierarchical_posterior(self):
        raw,out,r=execute()
        self.assertEqual(r.status,p.CONTINUOUS_SUCCESS)
        self.assertEqual([m.variable for m in r.moments],['global','urban','rural'])
        self.assertTrue(c.verify_continuous_receipt(raw,out).analytic_reference_checked)
        self.assertTrue(r.exact_gaussian_reference)
        self.assertGreater(r.moments[1].mean,r.moments[2].mean)
        self.assertGreater(r.moments[2].mean,0)

    def test_predictive_uncertainty_includes_measurement_noise(self):
        r=execute()[2]
        for m in r.moments[1:]:
            self.assertAlmostEqual(m.predictive_sd**2,m.sd**2+1.5**2,places=9)
        self.assertFalse(r.moments[0].predictive_sd)

    def test_no_observation_prior(self):
        req=request();req.model.ClearField('observations')
        raw,out,r=execute(req)
        self.assertEqual(r.status,p.CONTINUOUS_SUCCESS)
        self.assertAlmostEqual(r.moments[0].mean,0)
        self.assertAlmostEqual(r.moments[0].sd,2)
        self.assertAlmostEqual(r.moments[1].sd,math.sqrt(5))
        self.assertTrue(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_independent_random_gaussians(self):
        import random
        rng=random.Random(11039)
        for _ in range(45):
            req=request()
            req.model.global_prior_mean=rng.uniform(-10,10)
            req.model.global_prior_sd=rng.uniform(.3,5)
            req.model.group_sd=rng.uniform(.1,3)
            req.model.predictive_sd=rng.uniform(.2,3)
            req.model.ClearField('observations')
            for _ in range(rng.randrange(0,12)):
                req.model.observations.add(group=rng.randrange(2),value=rng.uniform(-10,10),known_sd=rng.uniform(.3,3))
            raw,out,r=execute(req)
            self.assertEqual(r.status,p.CONTINUOUS_SUCCESS)
            self.assertTrue(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_single_group_no_pooling_issue(self):
        req=request();del req.model.group_ids[1:]
        raw,out,r=execute(req)
        self.assertTrue(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_invalid_group(self):
        req=request();req.model.group_ids[1]=req.model.group_ids[0]
        self.assertEqual(execute(req)[2].status,p.CONTINUOUS_REJECTED)

    def test_invalid_observation_group(self):
        req=request();req.model.observations[0].group=17
        self.assertEqual(execute(req)[2].reason_code,'INVALID_OBSERVATIONS')

    def test_nonfinite_observations(self):
        for value in (float('nan'),float('inf')):
            req=request();req.model.observations[0].value=value
            self.assertEqual(execute(req)[2].status,p.CONTINUOUS_REJECTED)

    def test_impossible_prior_scale(self):
        req=request();req.model.group_sd=0
        self.assertEqual(execute(req)[2].reason_code,'INVALID_PRIOR')

    def test_extreme_outlier_still_valid(self):
        req=request();req.model.observations[0].value=100000
        raw,out,r=execute(req)
        self.assertEqual(r.status,p.CONTINUOUS_SUCCESS)
        self.assertTrue(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_auth_required(self):
        self.assertEqual(execute(authorized=False)[2].reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_disabled(self):
        self.assertEqual(execute(enabled=False)[2].reason_code,'PROBABILITY_DISABLED')

    def test_output_mutation(self):
        raw,out,r=execute();r.moments[0].mean+=2
        self.assertFalse(c.verify_continuous_receipt(raw,r.SerializeToString()).evidence_valid)

    def test_predictive_mutation(self):
        raw,out,r=execute();r.moments[1].predictive_sd+=1
        self.assertFalse(c.verify_continuous_receipt(raw,r.SerializeToString()).evidence_valid)

    def test_forged_exact_flag(self):
        raw,out,r=execute();r.exact_gaussian_reference=False
        self.assertFalse(c.verify_continuous_receipt(raw,r.SerializeToString()).evidence_valid)

    def test_forged_receipt(self):
        raw,out,r=execute()
        rec=c.verify_continuous_receipt(raw,out)
        rec.evidence_valid=False
        with self.assertRaises(ValueError):c.make_continuous_audit(raw,out,rec)

    def test_metadata_only_audit(self):
        raw,out,r=execute()
        audit=c.make_continuous_audit(raw,out)
        self.assertTrue(audit.exact_gaussian_reference)
        self.assertEqual(audit.request_sha256,hashlib.sha256(raw).digest())
        self.assertNotIn(b'urban',audit.SerializeToString())

    def test_budget_limit(self):
        req=request()
        for _ in range(129):req.model.observations.add(group=1,value=0,known_sd=1)
        self.assertEqual(execute(req)[2].reason_code,'INVALID_OBSERVATIONS')

    def test_without_independent_oracle_never_claims_proof(self):
        req=request()
        for _ in range(49):req.model.observations.add(group=1,value=0,known_sd=1)
        raw,out,r=execute(req)
        self.assertEqual(r.status,p.CONTINUOUS_SUCCESS)
        self.assertFalse(r.exact_gaussian_reference)
        self.assertFalse(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_optional_worker_default_off(self):
        self.assertEqual(execute(request(p.PYMC_NUTS))[2].reason_code,'PYMC_WORKER_DISABLED')

    def test_worker_digest_rejected(self):
        policy=c.WorkerPolicy(sys.executable,'bad','bad','bad','6.0',True)
        self.assertEqual(execute(request(p.PYMC_NUTS),policy=policy)[2].reason_code,'WORKER_INTEGRITY_MISMATCH')

    def test_advi_no_mix_diagnostics(self):
        req=request(p.PYMC_ADVI)
        raw,out,r=execute(req)
        self.assertEqual(r.status,p.CONTINUOUS_UNKNOWN)
        self.assertFalse(c.verify_continuous_receipt(raw,out).evidence_valid)

    def test_no_model_generated_executable(self):
        self.assertNotIn('executable',tuple(f.name for f in p.ContinuousRequest.DESCRIPTOR.fields))

    def test_backend_forbidden_zero_draws(self):
        req=request(p.PYMC_NUTS);req.draws=0
        self.assertEqual(execute(req)[2].status,p.CONTINUOUS_REJECTED)

    def test_tampered_backend(self):
        raw,out,r=execute();r.backend=p.PYMC_NUTS
        self.assertFalse(c.verify_continuous_receipt(raw,r.SerializeToString()).evidence_valid)

    def test_malformed_frame(self):
        self.assertEqual(p.ContinuousResult.FromString(c.run_continuous_frame(b'\xff',host_authorized=True,enabled=True)).status,p.CONTINUOUS_REJECTED)

    def test_optional_runtime_import_compatibility(self):
        # This environment has PyMC but incompatible ArviZ; not a live NUTS run.
        try:
            import pymc
        except ImportError:
            self.skipTest('PyMC + ArviZ incompatible; worker remains unvalidated')

if __name__=='__main__':unittest.main()
