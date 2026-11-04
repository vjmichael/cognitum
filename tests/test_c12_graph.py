"""C12 deterministic planning: gold plans, invalid model tests, independent oracle."""
import itertools
import unittest
from dataclasses import replace

from cognitum.planning_graph import (
    Action, PlanProblem, validate, transition, check_plan, plan,
)


def route():
    return PlanProblem(
        facts=("at_base","has_fuel","at_station","at_goal"),
        initial=("at_base","has_fuel"),
        goal=("at_goal",),
        goal_forbids=("at_base",),
        actions=(
            Action("move_station",requires=("at_base","has_fuel"),
                   add=("at_station",),delete=("at_base",),cost=2,risk=1),
            Action("move_goal",requires=("at_station","has_fuel"),
                   add=("at_goal",),delete=("at_station",),cost=2,risk=1),
            Action("direct",requires=("at_base","has_fuel"),
                   add=("at_goal",),delete=("at_base",),cost=9,risk=2),
        ),
        horizon=3,risk_budget=2,
    )


class C12GraphTests(unittest.TestCase):
    def test_weighted_search_finds_least_cost_and_replays(self):
        try:
            import networkx
        except ImportError:
            self.skipTest("NetworkX not installed")
        p=route()
        for algo in ("dijkstra","astar","dag_dp"):
            with self.subTest(algo=algo):
                result=plan(p,algorithm=algo)
                self.assertEqual(result.status,"OPTIMAL")
                self.assertEqual(result.total_cost,4)
                self.assertEqual(result.actions,("move_station","move_goal"))
                self.assertEqual(check_plan(p,result.actions)[:2],
                                 (result.final_state,result.total_cost))
        shortest_steps=plan(p,algorithm="bfs")
        self.assertEqual(shortest_steps.actions,("direct",))
        self.assertEqual(shortest_steps.total_cost,9)
        self.assertEqual(shortest_steps.status,"FEASIBLE")

    def test_preconditions_effects_and_risk(self):
        p=route()
        self.assertIsNone(transition(p,p.initial,p.actions[1]))
        self.assertIsNotNone(transition(p,p.initial,p.actions[0]))
        self.assertIsNone(check_plan(p,("move_goal",)))
        self.assertIsNone(check_plan(p,("move_station","direct")))
        self.assertIsNone(check_plan(replace(p,risk_budget=1),
                                     ("move_station","move_goal")))
        self.assertIsNone(check_plan(p,("not_an_action",)))
        self.assertIsNone(check_plan(p,("direct",)*4))

    def test_cyclic_search_stays_bounded_and_unreachable_honest(self):
        try:
            import networkx
        except ImportError:
            self.skipTest("NetworkX not installed")
        p=PlanProblem(
            facts=("a","b","goal"),
            initial=("a",),goal=("goal",),goal_forbids=(),
            actions=(Action("forward",requires=("a",),add=("b",),delete=("a",)),
                     Action("backward",requires=("b",),add=("a",),delete=("b",))),
            horizon=9,risk_budget=0,
        )
        result=plan(p)
        self.assertEqual(result.status,"UNREACHABLE_EXHAUSTIVE")
        self.assertLessEqual(result.expanded_states,4096)
        self.assertFalse(result.actions)

    def test_initial_goal_and_zero_horizon(self):
        try:
            import networkx
        except ImportError:
            self.skipTest("NetworkX not installed")
        p=PlanProblem(
            facts=("ready",),initial=("ready",),goal=("ready",),goal_forbids=(),
            actions=(Action("noop",requires=("ready",)),),horizon=0)
        result=plan(p)
        self.assertEqual(result.actions,())
        self.assertEqual(result.total_cost,0)
        self.assertEqual(result.status,"OPTIMAL")

    def test_plan_grammar_strict_and_no_code_execution(self):
        base=route()
        cases=(
            replace(base,facts=("duplicate","duplicate")),
            replace(base,horizon=13),
            replace(base,horizon=True),
            replace(base,risk_budget=31),
            replace(base,initial=("unknown",)),
            replace(base,goal_forbids=("at_goal",)),
            replace(base,actions=()),
            replace(base,actions=(Action("bad",requires=("unknown",)),)),
            replace(base,actions=(Action("bad",requires=("at_base",),
                                         forbids=("at_base",)),)),
            replace(base,actions=(Action("bad",add=("at_base",),delete=("at_base",)),)),
            replace(base,actions=(Action("bad",cost=0),)),
            replace(base,actions=(Action("bad",risk=True),)),
        )
        for case in cases:
            with self.subTest(case=repr(case)[:80]),self.assertRaises(ValueError):
                validate(case)
        with self.assertRaises(ValueError):
            plan(base,algorithm="invented_mcts")

    def test_independent_action_sequence_oracle(self):
        """Enumerate valid action sequences without using NetworkX shortest paths."""
        try:
            import networkx
        except ImportError:
            self.skipTest("NetworkX not installed")
        p=route()
        candidates=[]
        for length in range(p.horizon+1):
            for names in itertools.product((x.name for x in p.actions),repeat=length):
                result=check_plan(p,tuple(names))
                if result is not None:
                    candidates.append((result[1],tuple(names)))
        minimum=min(cost for cost,_ in candidates)
        self.assertEqual(minimum,plan(p,algorithm="dijkstra").total_cost)
        self.assertEqual(minimum,plan(p,algorithm="dag_dp").total_cost)

    def test_missing_optional_library(self):
        from unittest.mock import patch
        with patch.dict("sys.modules",{"networkx":None}):
            result=plan(route())
        self.assertEqual(result.status,"UNSUPPORTED")


if __name__=="__main__":
    unittest.main()
