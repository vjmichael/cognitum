"""COG-07 practical reject controls; actual native evidence runs separately."""
import unittest
import importlib.util
from unittest.mock import patch
import types,sys
from tests.test_c14_closeout import request,invoke

@unittest.skipUnless(importlib.util.find_spec('numpy'), 'C14 optional NumPy engine absent')
class PracticalCausalGuards(unittest.TestCase):
    def test_refuses_missing_backdoor_adjustment(self):
        q=request("ate_dowhy");del q.adjustment[:]
        with patch("cognitum.causal_specialists._estimate_dowhy") as backend:
            a=invoke(q)
            self.assertEqual((a.status,a.code),("invalid_input","unblocked_backdoor_path"))
            self.assertFalse(a.has_effect or a.has_interval);backend.assert_not_called()

    def test_refuses_post_treatment_adjustment(self):
        q=request("ate_dowhy")
        q.adjustment.append("X")
        q.graph_edges.add(source="T",target="X");q.graph_edges.add(source="X",target="Y")
        a=invoke(q)
        self.assertEqual((a.status,a.code),("invalid_input","post_treatment_adjustment"))
        self.assertFalse(a.has_effect)

    def test_refuses_collider_adjustment_opening_backdoor(self):
        q=request("ate_dowhy");del q.graph_edges[:];q.adjustment[:]=["X"]
        q.columns.append("V")
        for i,row in enumerate(q.rows):row.values.append(float(i%7))
        # T <- W -> X <- V -> Y; X also causes T. Conditioning on X
        # opens the collider path, despite X being a pre-treatment variable.
        for a,b in (("W","T"),("W","X"),("V","X"),("V","Y"),("X","T"),("T","Y")):
            q.graph_edges.add(source=a,target=b)
        a=invoke(q)
        self.assertEqual((a.status,a.code),("invalid_input","unblocked_backdoor_path"))
        self.assertFalse(a.has_effect or a.has_interval)

    def test_refuses_extrapolated_or_rank_deficient_econml(self):
        q=request("conditional_effect_econml");q.modifier_profile[0]=99.
        with patch("cognitum.causal_specialists._estimate_econml") as backend:
            self.assertEqual(invoke(q).code,"modifier_profile_outside_observed_support")
            q.modifier_profile[0]=.25
            for r in q.rows:r.values[3]=2*r.values[2]
            self.assertEqual(invoke(q).code,"rank_deficient_design")
            backend.assert_not_called()

    def test_bounded_numeric_input(self):
        q=request();q.rows[0].values[1]=1e200
        self.assertEqual(invoke(q).code,"numeric_range_exceeded")

    def test_refuses_invalid_pc_matrix(self):
        import numpy as np
        for matrix in (np.diag([1,0,0,0]),np.array([[0,0,0,0],[1,0,0,0],[0,0,0,0],[0,0,0,0]])):
            fake=types.SimpleNamespace(pc=lambda *a,**kw:types.SimpleNamespace(G=types.SimpleNamespace(graph=matrix)))
            with patch.dict(sys.modules,{"causallearn":types.ModuleType("causallearn"),
                 "causallearn.search":types.ModuleType("causallearn.search"),
                 "causallearn.search.ConstraintBased":types.ModuleType("causallearn.search.ConstraintBased"),
                 "causallearn.search.ConstraintBased.PC":fake}):
                result=invoke(request("discover_pc"))
                self.assertEqual((result.status,result.code),("error","malformed_graph"))
                self.assertFalse(result.discovered_edges or result.has_effect)

    def test_gpl_still_refused_without_host_license_policy(self):
        with patch("cognitum.causal_specialists._discover_pcmci") as backend:
            r=invoke(request("discover_pcmci"))
            self.assertEqual((r.status,r.code),("unavailable","license_review_required"))
            backend.assert_not_called()
