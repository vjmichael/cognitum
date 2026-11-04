"""C17 genuine heldout protocol: strictly past data for every prediction."""
import unittest
from dataclasses import replace

from cognitum.temporal_statespace import TemporalModel,TemporalSample,TemporalSequence
from cognitum.temporal_evaluation import evaluate_heldout


def sequence(n=60):
    return TemporalSequence(
        ("temperature",),tuple(
            TemporalSample(1000*i,(20.+.1*i,),
                           "sensor","obs_"+str(i)) for i in range(n)),
        "temporal_fixture","synthetic","unverified")


def model():
    return TemporalModel("constant_velocity",.001,.01,1,5,5000)


class C17HoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import scipy,numpy,sklearn
        except ImportError:raise unittest.SkipTest("optional real statistical libraries unavailable")

    def test_real_three_way_heldout_comparison(self):
        out=evaluate_heldout(sequence(),model(),train_count=40,
                              include_learned=True,host_admitted_training=True)
        self.assertEqual({x.model for x in out},{"last_value","kalman","ridge_ar"})
        for result in out:
            self.assertEqual(result.count,20)
            self.assertGreaterEqual(result.rmse,0)
            self.assertGreaterEqual(result.mean_wall_ms,0)
        baseline=next(x for x in out if x.model=="last_value")
        self.assertAlmostEqual(baseline.mae,.1,places=10)

    def test_training_needs_admission_and_unseen_labels(self):
        with self.assertRaises(PermissionError):
            evaluate_heldout(sequence(),model(),train_count=40,
                             include_learned=True,host_admitted_training=False)
        with self.assertRaises(ValueError):
            evaluate_heldout(sequence(),model(),train_count=59)

    def test_incomplete_truth_or_disorder_fail_closed(self):
        s=sequence()
        missing=replace(s,samples=s.samples[:44]+(
            replace(s.samples[44],values=(None,)),)+s.samples[45:])
        with self.assertRaises(ValueError):
            evaluate_heldout(missing,model(),train_count=40)
        ordered=list(s.samples)
        ordered[30]=replace(ordered[30],time_ms=31000)
        with self.assertRaises(ValueError):
            evaluate_heldout(replace(s,samples=tuple(ordered)),model(),train_count=40)


if __name__=="__main__":
    unittest.main()
