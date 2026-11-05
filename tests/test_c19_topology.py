"""C19 actual Ripser/SciPy/GUDHI persistence and fail-closed semantics."""
from dataclasses import replace
from math import pi,cos,sin
import unittest
from cognitum.topology_rips import (
    TopologyQuery,compute,validate,snapshot_hash,perturbation_stability,
)
from cognitum.topology_gudhi import crosscheck
from cognitum.topology_sensitivity import deterministic_farthest,check_sensitivity
from cognitum.topology_evaluation import benchmark

def query(points,scale=2.2,metric="euclidean",dim=1):
    return TopologyQuery("sample",snapshot_hash(points),"metres",metric,
                         "vietoris_rips",scale,dim,points)

def circle(n=20):
    return tuple((cos(2*pi*i/n),sin(2*pi*i/n)) for i in range(n))

class C19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import numpy,scipy,ripser,sklearn
        except ImportError:
            raise unittest.SkipTest("optional actual TDA dependencies missing")

    def test_true_circle_persistence_and_independent_mst(self):
        r=compute(query(circle()))
        self.assertEqual(r.status,"OK")
        self.assertEqual(r.connected_components_at_scale,1)
        self.assertEqual(len([x for x in r.intervals if x.dimension==0]),20)
        self.assertGreater(r.longest_finite_h1,.5)
        self.assertLess(r.h0_mst_max_deviation,1e-4)
        self.assertEqual(r.resource_pair_bound,190)

    def test_duplicate_and_degenerate_points(self):
        points=((0.,0.),(0.,0.),(0.,0.),(1.,0.),(1.,0.),(1.,0.))
        r=compute(query(points,1.5,dim=0))
        self.assertEqual(r.unique_points,2)
        self.assertEqual(r.connected_components_at_scale,1)
        self.assertEqual(len(r.intervals),6)
        # Exact duplicate samples produce zero-duration H0 merges even when
        # Ripser omits those ephemeral intervals from its raw diagram.
        h0=[x for x in r.intervals if x.dimension==0]
        self.assertEqual(sum(x.death==0. for x in h0),4)
        self.assertEqual(sum(x.death is not None and abs(x.death-1.)<1e-6
                             for x in h0),1)
        self.assertEqual(sum(x.death is None for x in h0),1)
        self.assertLess(r.h0_mst_max_deviation,1e-6)

    def test_duplicate_points_disconnected_under_small_threshold(self):
        points=((0.,0.),(0.,0.),(5.,0.),(5.,0.),(10.,0.),(10.,0.))
        r=compute(query(points,.1,dim=0))
        self.assertEqual(r.status,"OK")
        self.assertEqual(r.unique_points,3)
        self.assertEqual(r.connected_components_at_scale,3)
        self.assertEqual(sum(x.dimension==0 and x.death==0
                             for x in r.intervals),3)
        self.assertEqual(sum(x.dimension==0 and x.death is None
                             for x in r.intervals),3)

    def test_metric_and_threshold_change_interpretation(self):
        points=((0.,0.),(3.,0.),(0.,3.),(3.,3.))
        r=compute(query(points,.2,dim=0))
        self.assertEqual(r.connected_components_at_scale,4)
        a=compute(query(points,3.5,metric="euclidean",dim=0))
        b=compute(query(points,3.5,metric="manhattan",dim=0))
        self.assertEqual(a.connected_components_at_scale,1)
        self.assertEqual(b.connected_components_at_scale,1)
        self.assertEqual(a.metric,"euclidean")
        self.assertEqual(b.metric,"manhattan")

    def test_invalid_scale_nonfinite_snapshot_and_excessive_complexity(self):
        q=query(circle())
        for bad in (replace(q,maximum_scale=float("nan")),
                    replace(q,maximum_scale=0.),
                    replace(q,maximum_homology_dimension=2),
                    replace(q,filtration="arbitrary_python"),
                    replace(q,points=q.points[:10]),
                    replace(q,points=((float("inf"),0.),)+q.points[1:]),
                    replace(q,max_points=2),
                    replace(q,metric="cosine")):
            with self.subTest(bad=str(bad)[:65]),self.assertRaises(ValueError):
                validate(bad)

    def test_perturbation_stability_real_diagram_distance(self):
        original=circle()
        perturbed=tuple((x+.002,y-.002) for x,y in original)
        d=perturbation_stability(query(original),query(perturbed))
        self.assertEqual(len(d),2)
        self.assertLess(max(d),.001)

    def test_deterministic_subsampling_and_real_bottleneck_sensitivity(self):
        q=query(circle(20))
        idx,reduced=deterministic_farthest(q,15)
        self.assertEqual(len(set(idx)),15)
        self.assertEqual(idx[0],0)
        self.assertEqual(deterministic_farthest(q,15)[0],idx)
        observed=check_sensitivity(q,keep=15)
        self.assertEqual(observed.status,"MEASURED")
        self.assertEqual(observed.sample_retained,15)
        self.assertEqual(len(observed.bottleneck_by_dimension),2)
        self.assertTrue(all(x>=0 for x in observed.bottleneck_by_dimension))
        with self.assertRaises(ValueError):
            deterministic_farthest(q,2)

    def test_independent_gudhi_matches_ripser_for_small_circle(self):
        try:import gudhi
        except ImportError:self.skipTest("GUDHI optional verifier not installed")
        r=crosscheck(query(circle(16)))
        self.assertEqual(r.status,"MATCH")
        self.assertLess(r.maximum_endpoint_deviation,1e-4)

    def test_real_heldout_benchmark_has_all_incumbents(self):
        b=benchmark(ntrain=12,ntest=8)
        self.assertEqual(b.status,"MEASURED_SYNTHETIC_ONLY")
        self.assertEqual({x.model for x in b.results},
            {"geometry","geometry_spectral","geometry_topology",
             "geometry_spectral_topology"})
        self.assertTrue(all(0<=x.holdout_accuracy<=1 for x in b.results))

if __name__=="__main__":
    unittest.main()
