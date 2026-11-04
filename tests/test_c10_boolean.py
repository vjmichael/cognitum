"""C10 bounded Boolean proof-status regression suite (no Lu host claims)."""
from dataclasses import replace
import itertools
import unittest

from cognitum.formal_boolean import CNF, Decision, solve, verify, evaluates_true


class C10BooleanTests(unittest.TestCase):
    def test_sat_witness_and_independent_replay(self):
        f=CNF(3, ((1, 2), (-1, 3), (-2, 3), (3,)))
        d=solve(f)
        self.assertEqual(d.status,"SAT")
        self.assertTrue(verify(f,d))
        self.assertTrue(evaluates_true(f,d.assignment))
        self.assertFalse(verify(f,replace(d,assignment=tuple(not x for x in d.assignment))))

    def test_unsat_exhaustion_and_forgery(self):
        f=CNF(2, ((1,),(-1,)))
        d=solve(f)
        self.assertEqual(d.status,"UNSAT_EXHAUSTIVE")
        self.assertEqual(d.checked_assignments,4)
        self.assertTrue(verify(f,d))
        self.assertFalse(verify(CNF(2, ((1,),)),d))
        self.assertFalse(verify(f,replace(d,checked_assignments=2)))

    def test_empty_clause_and_tautologies(self):
        self.assertEqual(solve(CNF(1,((),))).status,"UNSAT_EXHAUSTIVE")
        self.assertEqual(solve(CNF(1,((1,-1),))).status,"SAT")
        self.assertEqual(solve(CNF(2,())).status,"SAT")
        self.assertTrue(verify(CNF(1,((),)),solve(CNF(1,((),)))))

    def test_budget_unknown_not_false_unsat(self):
        f=CNF(3,((1,),(2,),(3,)))
        d=solve(f,assignment_budget=2)
        self.assertEqual(d.status,"UNKNOWN_BUDGET")
        self.assertTrue(verify(f,d))
        self.assertFalse(d.assignment)
        self.assertEqual(solve(f,assignment_budget=8).status,"SAT")

    def test_all_two_variable_boolean_functions(self):
        # Independent oracle: Python assignment product in a different order.
        clauses=((1,),(-1,),(2,),(-2,),(1,2),(-1,2),(1,-2),(-1,-2),())
        for i in range(1 << len(clauses)):
            selected=tuple(c for j,c in enumerate(clauses) if i & (1 << j))
            f=CNF(2,selected)
            expected=any(all(any(values[abs(lit)-1] == (lit>0) for lit in clause)
                             for clause in selected)
                         for values in itertools.product((False,True),repeat=2))
            d=solve(f)
            self.assertEqual(d.status=="SAT",expected)
            self.assertTrue(verify(f,d))

    def test_invalid_formula_rejected_before_decision(self):
        bad=(CNF(0,()),CNF(13,()),CNF(True,()),CNF(1,[]),
             CNF(1,([1],)),CNF(1,((0,),)),CNF(1,((2,),)),
             CNF(1,((True,),)),CNF(1,((1,)*257,)),CNF(1,((1,),)*65))
        for f in bad:
            with self.subTest(f=repr(f)[:80]),self.assertRaises(ValueError):
                solve(f)
        for budget in (0,-1,4097,True):
            with self.assertRaises(ValueError):
                solve(CNF(1,()),assignment_budget=budget)

    def test_witness_type_and_assurance_tampering_rejected(self):
        f=CNF(2,((1,),(2,)))
        d=solve(f)
        for forged in (replace(d,assignment=(1,True)),
                       replace(d,assurance="proved"),
                       replace(d,limitations=()),
                       replace(d,status="UNSAT_EXHAUSTIVE"),
                       replace(d,checked_assignments=True)):
            self.assertFalse(verify(f,forged))

    def test_no_dynamic_execution_or_tool_registration(self):
        import inspect
        import cognitum.formal_boolean as formal
        source=inspect.getsource(formal)
        for token in ("eval(", "exec(", "subprocess", "os.system", "import z3"):
            self.assertNotIn(token,source)
        from cognitum.plugins.calculator import Calculator
        self.assertEqual([op.name for op in Calculator().manifest().operations],
                         ["calc.rational"])


if __name__=="__main__":
    unittest.main()
