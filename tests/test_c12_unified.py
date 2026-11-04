"""C12 independent Unified Planning validation: real library, no mocks."""
import unittest
from dataclasses import replace

from cognitum.planning_graph import Action,PlanProblem,plan
from cognitum.planning_unified import verify_with_unified_planning


def fixture():
    return PlanProblem(
        facts=("start","mid","done"),initial=("start",),
        goal=("done",),goal_forbids=("start",),
        actions=(
            Action("move",requires=("start",),add=("mid",),delete=("start",),risk=1),
            Action("finish",requires=("mid",),add=("done",),delete=("mid",),risk=1),
            Action("shortcut",requires=("start",),add=("done",),delete=("start",),cost=5,risk=2),
        ),horizon=3,risk_budget=2,
    )


class C12UnifiedPlanningTests(unittest.TestCase):
    def test_real_external_validator_positive_and_negative(self):
        try:
            import unified_planning
        except ImportError:
            self.skipTest("Unified Planning not installed")
        p=fixture()
        self.assertEqual(verify_with_unified_planning(p,("move","finish")),"VALID")
        self.assertEqual(verify_with_unified_planning(p,("finish",)),"INVALID")
        self.assertEqual(verify_with_unified_planning(p,("move",)),"INVALID")
        self.assertEqual(verify_with_unified_planning(p,("unknown",)),"INVALID")

    def test_risk_budget_still_checked_independently(self):
        try:
            import unified_planning
        except ImportError:
            self.skipTest("Unified Planning not installed")
        p=replace(fixture(),risk_budget=0)
        self.assertEqual(verify_with_unified_planning(p,("move","finish")),"INVALID")
        self.assertEqual(verify_with_unified_planning(p,()),"INVALID")

    def test_candidate_from_real_graph_engine_validates_through_second_library(self):
        try:
            import unified_planning, networkx
        except ImportError:
            self.skipTest("planning packages missing")
        p=fixture()
        result=plan(p,algorithm="dijkstra")
        self.assertEqual(result.status,"OPTIMAL")
        self.assertEqual(verify_with_unified_planning(p,result.actions),"VALID")


if __name__=="__main__":
    unittest.main()
