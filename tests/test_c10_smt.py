"""C10 typed linear-integer SMT adapters: exact witness checks and real backends."""
import unittest

from cognitum.formal_smt import (
    IntVar, LinearAtom, SMTProblem, validate, satisfies, exhaustive, solve,
)


class C10SMTTests(unittest.TestCase):
    def test_independent_exhaustive_integer_engine(self):
        p=SMTProblem(
            (IntVar("x",-3,3),IntVar("y",-3,3)),
            (LinearAtom((("x",1),("y",1)),"eq",2),
             LinearAtom((("x",1),),"ge",0)))
        result=solve(p,backend="exhaustive")
        self.assertEqual(result.status,"SAT")
        self.assertTrue(satisfies(p,result.witness))
        self.assertFalse(satisfies(p,(9,9)))

    def test_unsat_is_independently_exhausted(self):
        p=SMTProblem((IntVar("x",0,4),),
                     (LinearAtom((("x",1),),"lt",1),
                      LinearAtom((("x",1),),"gt",3)))
        self.assertEqual(exhaustive(p),())
        self.assertEqual(solve(p,backend="exhaustive").status,"UNSAT_EXHAUSTIVE")

    def test_bounded_unknown_not_unsat(self):
        p=SMTProblem((IntVar("x",0,32),IntVar("y",0,32),IntVar("z",0,32)),())
        self.assertIsNone(exhaustive(p))
        self.assertEqual(solve(p,backend="exhaustive").status,"UNKNOWN")

    def test_bad_input_and_solver_options(self):
        for p in (
            SMTProblem((IntVar("x",0,33),),()),
            SMTProblem((IntVar("x",0,1),IntVar("x",0,1)),()),
            SMTProblem((IntVar("x",True,1),),()),
            SMTProblem((IntVar("x",0,1),),(LinearAtom((("q",1),),"eq",0),)),
            SMTProblem((IntVar("x",0,1),),(LinearAtom((("x",1),("x",2)),"eq",0),)),
            SMTProblem((IntVar("x",0,1),),(LinearAtom((("x",True),),"eq",0),)),
        ):
            with self.subTest(p=repr(p)),self.assertRaises(ValueError):
                validate(p)
        p=SMTProblem((IntVar("x",0,1),),())
        with self.assertRaises(ValueError):
            solve(p,timeout_ms=0)
        self.assertEqual(solve(p,backend="unsupported").status,"UNSUPPORTED")

    def test_optional_native_z3(self):
        try:
            import z3
        except ImportError:
            self.skipTest("z3 not installed")
        p=SMTProblem((IntVar("x",0,5),),
                     (LinearAtom((("x",1),),"eq",4),))
        sat=solve(p,backend="z3")
        self.assertEqual(sat.status,"SAT")
        self.assertEqual(sat.witness,(4,))
        neg=SMTProblem(p.integers,p.atoms+(LinearAtom((("x",1),),"eq",3),))
        self.assertEqual(solve(neg,backend="z3").status,"UNSAT_EXHAUSTIVE")

    def test_optional_solver_negative_integer_witness(self):
        for backend, module in (("z3","z3"),("cvc5","cvc5")):
            try:
                __import__(module)
            except ImportError:
                continue
            p=SMTProblem((IntVar("x",-5,5),),
                         (LinearAtom((("x",1),),"eq",-3),))
            with self.subTest(backend=backend):
                d=solve(p,backend=backend)
                self.assertEqual(d.status,"SAT")
                self.assertEqual(d.witness,(-3,))
                self.assertTrue(satisfies(p,d.witness))

    def test_optional_native_cvc5(self):
        try:
            import cvc5
        except ImportError:
            self.skipTest("cvc5 not installed")
        p=SMTProblem((IntVar("x",0,5),),
                     (LinearAtom((("x",1),),"eq",4),))
        result=solve(p,backend="cvc5")
        self.assertEqual(result.status,"SAT")
        self.assertEqual(result.witness,(4,))
        neg=SMTProblem(p.integers,p.atoms+(LinearAtom((("x",1),),"eq",3),))
        self.assertEqual(solve(neg,backend="cvc5").status,"UNSAT_EXHAUSTIVE")


if __name__=="__main__":
    unittest.main()
