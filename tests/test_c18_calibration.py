"""C18 real SciPy middle-window calibration, no heldout label reuse."""
from dataclasses import replace
from math import isfinite
import unittest

from cognitum.adaptation_policy import (
    Trace,AdaptationProposal,RoutingPolicy,seal,train,
)
from cognitum.adaptation_calibration import fit,evaluate,verify

SHA="a"*64

def fixture():
    base=seal(RoutingPolicy(1,"workspace","tool_router",("general",),2,
        ((0.,0.),(0.,0.),(0.,0.)),(.4,0.,0.),(0.,0.),(1.,1.),
        "b"*64,"original","0"*64,"approved",""))
    p=AdaptationProposal("calibration_proposal","workspace","tool_router",
        2,SHA,"consent_a","public_synthetic",("general",),200000,
        66000,86000,base.digest,80,120000,base.digest)
    labels=("direct","specialist","abstain")
    rows=tuple(Trace("event_"+str(i),1000*(i+1),
         (float((i%3-1)*3),float(i%3-1)),
         labels[i%3],SHA,"consent_a",200000,"public_synthetic","general")
         for i in range(120))
    training_and_future=rows[:65]+rows[85:]
    candidate,hold=train(p,training_and_future,now_ms=130000,host_authorized=True)
    return p,candidate,rows[65:85],hold

class C18CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import scipy,numpy,sklearn
        except ImportError:
            raise unittest.SkipTest("SciPy and scikit-learn optional calibration backend absent")

    def test_fit_middle_window_and_evaluate_only_future(self):
        p,model,middle,future=fixture()
        with self.assertRaises(PermissionError):
            fit(p,model,middle)
        artifact=fit(p,model,middle,host_authorized=True)
        self.assertEqual(verify(artifact,model),artifact)
        self.assertGreaterEqual(artifact.temperature,.25)
        self.assertLessEqual(artifact.temperature,5)
        stats=evaluate(p,model,artifact,future)
        self.assertEqual(stats.count,35)
        self.assertTrue(all(isfinite(x) and x>=0 for x in
                            (stats.raw_log_loss,stats.calibrated_log_loss,
                             stats.raw_brier,stats.calibrated_brier)))

    def test_corrupt_artifact_and_calibration_leakage_refused(self):
        p,model,middle,future=fixture()
        a=fit(p,model,middle,host_authorized=True)
        with self.assertRaises(ValueError):
            verify(replace(a,temperature=999.),model)
        with self.assertRaises(ValueError):
            verify(replace(a,temperature=a.temperature+.3),model)
        with self.assertRaises(ValueError):
            fit(p,model,future[:12],host_authorized=True)
        with self.assertRaises(ValueError):
            evaluate(p,model,a,middle)
        with self.assertRaises(ValueError):
            fit(p,model,(replace(middle[0],source_digest="b"*64),)+middle[1:],
                host_authorized=True)

if __name__=="__main__":
    unittest.main()
