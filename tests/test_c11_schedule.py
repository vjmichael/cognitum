"""C11 OR-Tools scheduling regression with independent feasibility oracle."""
from dataclasses import replace
from itertools import product
import unittest

from cognitum.optimization_schedule import (
    Job, ScheduleProblem, ScheduledJob, validate, verify_schedule, optimize_schedule,
)


def simple():
    return ScheduleProblem(10,("a","b"),(
        Job("cut",3,0,7,("a","b")),
        Job("assemble",2,1,10,("a","b"),("cut",)),
        Job("paint",2,0,10,("b",)),
    ))


class C11ScheduleTests(unittest.TestCase):
    def test_independent_schedule_checker(self):
        problem=simple()
        good=(ScheduledJob("cut","a",0,3),
              ScheduledJob("assemble","a",3,5),
              ScheduledJob("paint","b",0,2))
        self.assertTrue(verify_schedule(problem,good))
        self.assertFalse(verify_schedule(problem,good+(good[0],)))
        self.assertFalse(verify_schedule(problem,good[:-1]))
        self.assertFalse(verify_schedule(problem,(good[0],replace(good[1],start=2,end=4),good[2])))
        self.assertFalse(verify_schedule(problem,(good[0],good[1],replace(good[2],resource="a",start=1,end=3))))
        self.assertFalse(verify_schedule(problem,(good[0],good[1],replace(good[2],resource="missing"))))

    def test_bad_inputs_and_cycles(self):
        root=simple()
        invalid=(
            replace(root,horizon=129),
            replace(root,unit="minutes_since_epoch"),
            replace(root,resources=("a","a")),
            replace(root,jobs=(Job("bad",0,0,2,("a",)),)),
            replace(root,jobs=(Job("bad",2,3,2,("a",)),)),
            replace(root,jobs=(Job("bad",1,0,2,("unknown",)),)),
            replace(root,jobs=(Job("same",1,0,2,("a",)),Job("same",1,0,2,("b",)))),
            replace(root,jobs=(Job("x",1,0,3,("a",),("y",)),
                               Job("y",1,0,3,("a",),("x",)))),
            replace(root,jobs=(Job("x",1,0,3,("a",),("doesnt_exist",)),)),
        )
        for p in invalid:
            with self.subTest(problem=repr(p)[:100]),self.assertRaises(ValueError):
                validate(p)
        for budget in (0,10001,True):
            with self.assertRaises(ValueError):
                optimize_schedule(root,time_limit_ms=budget)

    def test_native_ortools_solution_and_optimality(self):
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            self.skipTest("OR-Tools not installed")
        result=optimize_schedule(simple(),time_limit_ms=5000)
        self.assertEqual(result.status,"OPTIMAL")
        self.assertTrue(verify_schedule(simple(),result.assignments))
        self.assertEqual(result.makespan,5)
        self.assertLessEqual(result.solver_bound,result.makespan)

    def test_native_infeasible(self):
        try:
            import ortools
        except ImportError:
            self.skipTest("OR-Tools not installed")
        # Both tasks require the same single resource and must finish in 2 slots.
        problem=ScheduleProblem(2,("only",),(
            Job("a",2,0,2,("only",)),
            Job("b",2,0,2,("only",)),
        ))
        self.assertEqual(optimize_schedule(problem,time_limit_ms=5000).status,"INFEASIBLE")

    def test_independent_brute_force_optimum(self):
        """Tiny cross-product schedule oracle, not OR-Tools itself."""
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            self.skipTest("OR-Tools not installed")
        problem=ScheduleProblem(6,("a","b"),(
            Job("first",2,0,6,("a","b")),
            Job("second",1,0,6,("a","b"),("first",)),
            Job("third",2,1,6,("a","b")),
        ))
        options=[]
        for job in problem.jobs:
            options.append([ScheduledJob(job.name,res,start,start+job.duration)
                            for res in job.eligible_resources
                            for start in range(job.release,job.deadline-job.duration+1)])
        opt=min(max(a.end for a in candidate)
                for candidate in product(*options)
                if verify_schedule(problem,tuple(candidate)))
        actual=optimize_schedule(problem,time_limit_ms=5000)
        self.assertEqual(actual.status,"OPTIMAL")
        self.assertEqual(actual.makespan,opt)


if __name__=="__main__":
    unittest.main()
