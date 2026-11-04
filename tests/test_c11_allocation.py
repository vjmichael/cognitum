"""C11 SciPy HiGHS allocation regression; independent exact brute-force oracle."""
from dataclasses import replace
from itertools import product
import unittest

from cognitum.optimization_allocation import (
    Quantity, ResourceConstraint, AllocationProblem, AllocationResult,
    validate, verify_allocation, minimize_allocation,
)


def supply():
    # Choose least-cost two units; A max 1, B max 3.
    return AllocationProblem(
        (Quantity("a",0,1,5),Quantity("b",0,3,2)),
        (ResourceConstraint((1,1),"ge",2),
         ResourceConstraint((1,0),"le",1)),
    )


class C11AllocationTests(unittest.TestCase):
    def test_exact_constraints_and_objective(self):
        p=supply()
        self.assertTrue(verify_allocation(p,(0,2)))
        self.assertTrue(verify_allocation(p,(1,1)))
        for values in ((0,1),(2,0),(1,4),(-1,3),(1.0,1),(True,2),(0,)):
            self.assertFalse(verify_allocation(p,values))

    def test_invalid_model_rejections(self):
        base=supply()
        invalid=(
            replace(base,quantities=()),
            replace(base,unit="hours_and_kg"),
            replace(base,quantities=(Quantity("a",0,1,5),Quantity("a",0,2,1))),
            replace(base,quantities=(Quantity("a",-1,1,5),)),
            replace(base,quantities=(Quantity("a",0,101,5),)),
            replace(base,constraints=(ResourceConstraint((1,), "ge", 2),)),
            replace(base,constraints=(ResourceConstraint((1,1),"unknown",2),)),
            replace(base,constraints=(ResourceConstraint((True,1),"ge",2),)),
        )
        for p in invalid:
            with self.subTest(p=repr(p)),self.assertRaises(ValueError):
                validate(p)
        for budget in (0,10001,True):
            with self.assertRaises(ValueError):
                minimize_allocation(base,time_limit_ms=budget)

    def test_native_highs_optimal_and_independent_oracle(self):
        try:
            import scipy
        except ImportError:
            self.skipTest("SciPy not installed")
        p=supply()
        result=minimize_allocation(p,time_limit_ms=5000)
        self.assertEqual(result.status,"OPTIMAL")
        self.assertEqual(result.values,(0,2))
        self.assertEqual(result.objective,4)
        brute=min(
            sum(q.cost*x for q,x in zip(p.quantities,v))
            for v in product(*(range(q.lower,q.upper+1) for q in p.quantities))
            if verify_allocation(p,tuple(v)))
        self.assertEqual(result.objective,brute)

    def test_native_infeasible(self):
        try:
            import scipy
        except ImportError:
            self.skipTest("SciPy not installed")
        p=AllocationProblem(
            (Quantity("x",0,2,1),),
            (ResourceConstraint((1,),"le",0),
             ResourceConstraint((1,),"ge",2)))
        self.assertEqual(minimize_allocation(p,time_limit_ms=5000).status,"INFEASIBLE")

    def test_negative_cost_still_respects_upper_bounds(self):
        try:
            import scipy
        except ImportError:
            self.skipTest("SciPy not installed")
        p=AllocationProblem((Quantity("x",0,3,-2),),())
        result=minimize_allocation(p,time_limit_ms=5000)
        self.assertEqual(result.status,"OPTIMAL")
        self.assertEqual(result.values,(3,))
        self.assertEqual(result.objective,-6)


if __name__=="__main__":
    unittest.main()
