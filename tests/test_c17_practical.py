"""C17 conventional state-space, HMM, and learned temporal regression."""
from dataclasses import replace
from math import isfinite
import unittest

from cognitum.temporal_statespace import (
    TemporalSample,TemporalSequence,TemporalModel,filter_sequence,validate,
)
from cognitum.temporal_hidden import (
    HiddenObservation,HiddenStateModel,infer_hidden,validate_hmm,
)
from cognitum.temporal_learned import (
    train_ridge,forecast,verify_artifact,StateArtifact,
)


def series(n=40,missing=False,shift=False):
    events=[]
    for i in range(n):
        value=(float(i)*.5 if i<28 else (float(i)*.5+30 if shift else float(i)*.5))
        events.append(TemporalSample(1000*i,
            (None if missing and i in (5,7,8) else value,),
            "sensor_a","ob"+str(i)))
    return TemporalSequence(("metres",),tuple(events),"run1","synthetic","unverified")


def local_model(kind="local_level"):
    return TemporalModel(kind,.04,.05,1.,3.,60000)


def hmm():
    return HiddenStateModel(
        ("normal","alarm"),(.9,.1),
        ((.95,.05),(.05,.95)),
        ((.95,.05),(.05,.95)),
        1000,"declared_transition")


class C17StateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy, scipy
        except ImportError:
            raise unittest.SkipTest("optional genuine C17 numerical/learning backend not installed")

    def test_real_kalman_local_and_constant_velocity(self):
        try: import scipy,numpy
        except ImportError:self.skipTest("NumPy/SciPy not installed")
        s=series(missing=True)
        for method in ("local_level","constant_velocity"):
            with self.subTest(method=method):
                result=filter_sequence(s,local_model(method),forecast_time_ms=41000)
                self.assertEqual(result.status,"OK")
                self.assertEqual(len(result.points),40)
                self.assertEqual(result.missing_count,3)
                self.assertEqual(result.observed_count,37)
                self.assertEqual(len(result.forecast_mean),1)
                self.assertGreater(result.forecast_variance[0],0)
                self.assertGreaterEqual(result.points[5].posterior_variance[0],
                                        result.points[4].posterior_variance[0])

    def test_bootstrap_observation_counted_once_and_no_lookahead(self):
        s=series(40)
        out=filter_sequence(s,local_model(),forecast_time_ms=40000)
        self.assertEqual(out.points[0].posterior_mean,(0.,))
        self.assertEqual(out.points[0].posterior_variance,(1.,))
        self.assertEqual(out.observed_count,40)
        first_missing=replace(s,samples=(replace(s.samples[0],values=(None,)),)+s.samples[1:])
        with self.assertRaises(ValueError):
            validate(first_missing,local_model())

    def test_anomalous_evidence_is_not_silently_assimilated(self):
        s=series(shift=True)
        result=filter_sequence(s,local_model(),forecast_time_ms=40000)
        self.assertEqual(result.status,"OK")
        self.assertGreater(result.anomalies_count,0)
        self.assertTrue(result.ood)
        self.assertTrue(any(p.anomalies[0] for p in result.points))
        self.assertTrue(any(abs(z)>3 for p in result.points for z in p.normalized_innovation
                            if z is not None))

    def test_reordering_duplicate_lineage_and_nan_refused(self):
        s=series()
        for bad in (
            replace(s,samples=s.samples[:10]+(s.samples[9],)+s.samples[11:]),
            replace(s,samples=s.samples[:3]+(replace(s.samples[3],
                         observation_id=s.samples[2].observation_id),)+s.samples[4:]),
            replace(s,samples=s.samples[:3]+(replace(s.samples[3],
                         values=(float("nan"),)),)+s.samples[4:]),
            replace(s,units=("bad unit",)),
            replace(s,quality_declared="verified_truth"),
        ):
            with self.subTest(bad=repr(bad)[:80]),self.assertRaises(ValueError):
                validate(bad,local_model())

    def test_forecast_refuses_backwards_or_excessive_horizon(self):
        for t in (-1,39000,40000+60001):
            with self.assertRaises(ValueError):
                filter_sequence(series(),local_model(),forecast_time_ms=t)

    def test_multichannel_dimension_and_missingness(self):
        s=series()
        dual=replace(s,units=("metres","kelvin"),samples=tuple(
            replace(x,values=(x.values[0],300+i*.1)) for i,x in enumerate(s.samples)))
        out=filter_sequence(dual,local_model(),forecast_time_ms=40000)
        self.assertEqual(out.status,"OK")
        self.assertEqual(len(out.forecast_mean),2)
        with self.assertRaises(ValueError):
            validate(replace(dual,units=("metres",)),local_model())


class C17HiddenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy, scipy
        except ImportError:
            raise unittest.SkipTest("optional genuine C17 numerical/learning backend not installed")

    def test_hmm_state_changes_not_semantic_truth(self):
        obs=tuple(HiddenObservation(1000*i,0 if i<10 else 1,
                                   "sensor","obs"+str(i)) for i in range(20))
        result=infer_hidden(hmm(),obs)
        self.assertEqual(result.status,"OK")
        self.assertEqual(result.probable_states[0],"normal")
        self.assertEqual(result.probable_states[-1],"alarm")
        self.assertGreaterEqual(sum(result.change_alerts),1)
        self.assertAlmostEqual(sum(result.posteriors[-1]),1,places=12)
        self.assertIn("state_labels_not_semantic_event_truth",result.limitations)

    def test_stationary_hmm_does_not_invent_change_point(self):
        obs=tuple(HiddenObservation(1000*i,0,"sensor","stable_"+str(i))
                  for i in range(60))
        result=infer_hidden(hmm(),obs,alert_probability=.9)
        self.assertEqual(result.status,"OK")
        self.assertEqual(result.probable_states[0],"normal")
        self.assertEqual(result.probable_states[-1],"normal")
        self.assertFalse(any(result.change_alerts))

    def test_missing_emission_and_impossible_evidence(self):
        obs=tuple(HiddenObservation(1000*i,None if i in (3,7) else 0,
                                   "sensor","obs"+str(i)) for i in range(12))
        self.assertEqual(infer_hidden(hmm(),obs).status,"OK")
        bad=replace(hmm(),emissions=((1.,0.),(1.,0.)))
        obs=tuple(HiddenObservation(1000*i,1,"sensor","obs"+str(i))
                  for i in range(4))
        self.assertEqual(infer_hidden(bad,obs).status,"IMPOSSIBLE_EVIDENCE")

    def test_hmm_invalid_transition_time_and_prior(self):
        obs=tuple(HiddenObservation(1000*i,0,"sensor","obs"+str(i))
                  for i in range(8))
        for model,data in (
            (replace(hmm(),prior=(.5,.6)),obs),
            (replace(hmm(),transitions=((.9,.9),(.1,.9))),obs),
            (hmm(),obs[:2]+(replace(obs[2],time_ms=1500),)+obs[3:]),
            (hmm(),obs[:2]+(replace(obs[2],category=True),)+obs[3:]),
        ):
            with self.subTest(model=repr(model)[:65]),self.assertRaises(ValueError):
                validate_hmm(model,data)


class C17LearnedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy, scipy
            import sklearn
        except ImportError:
            raise unittest.SkipTest("optional genuine C17 numerical/learning backend not installed")

    def test_trained_checkpoint_and_recursive_forecast(self):
        try:import sklearn
        except ImportError:self.skipTest("scikit-learn optional backend not installed")
        s=series(n=60)
        with self.assertRaises(PermissionError):
            train_ridge(s,train_count=40)
        art=train_ridge(s,train_count=40,host_admitted=True)
        self.assertEqual(verify_artifact(art),art)
        p=forecast(art,replace(s,samples=s.samples[:40]),steps=5)
        self.assertEqual(p.status,"OK")
        self.assertEqual(len(p.means),5)
        self.assertTrue(all(isfinite(x[0]) for x in p.means))

    def test_checkpoint_tamper_and_train_split_rejected(self):
        try:import sklearn
        except ImportError:self.skipTest("scikit-learn optional backend not installed")
        s=series(60)
        art=train_ridge(s,train_count=40,host_admitted=True)
        with self.assertRaises(ValueError):
            verify_artifact(replace(art,coefficients=((500.,500.,500.),)))
        altered=list(s.samples)
        altered[10]=replace(altered[10],values=(999.,))
        with self.assertRaises(ValueError):
            forecast(art,replace(s,samples=tuple(altered)),steps=2)
        with self.assertRaises(ValueError):
            train_ridge(s,train_count=59,host_admitted=True)

    def test_learned_missing_and_irregular_time_refused(self):
        try:import sklearn
        except ImportError:self.skipTest("scikit-learn optional backend not installed")
        with self.assertRaises(ValueError):
            train_ridge(series(60,missing=True),train_count=40,host_admitted=True)
        s=series(60)
        samples=list(s.samples)
        samples[15]=replace(samples[15],time_ms=14500)
        with self.assertRaises(ValueError):
            train_ridge(replace(s,samples=tuple(samples)),train_count=40,host_admitted=True)


if __name__=="__main__":
    unittest.main()
