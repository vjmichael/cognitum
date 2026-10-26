from fractions import Fraction
import unittest
from cognitum.plugins.calculator import Calculator, calculate

class CalculatorTests(unittest.TestCase):
    def test_self_test(self):
        self.assertTrue(Calculator().self_test())

    def test_known_arithmetic(self):
        cases = {"0.1+0.2": "3/10", "1/3 + 1/6": "1/2", "2**-3": "1/8",
                 "-(2+3)*4": "-20", "7/2": "7/2", "9007199254740993+1": "9007199254740994",
                 "2+3*4": "14", "0**0": "1"}
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression), expected)

    def test_generated_fraction_control(self):
        # Independent Fraction construction across signs, denominators and operations.
        for a in range(-8, 9):
            for b in range(1, 9):
                with self.subTest(a=a, b=b):
                    self.assertEqual(calculate(f"({a}/{b}) + (3/7)"), str(Fraction(a, b) + Fraction(3, 7)))

    def test_reject_syntax_and_resource_attacks(self):
        cases = ["__import__('os')", "open('secret')", "(1).__class__", "[1,2]", "True", "x+1",
                 "1/0", "2**1000000", "9**9**9", "1e9999999", "1e-999999", "2**0.5",
                 "0**-1", "1//2", "1%2", "0xff", "1_000", "1+" * 100 + "1", "1"*257,
                 "("*100 + "1" + ")"*100, "", "   ", "lambda:1"]
        for expression in cases:
            with self.subTest(expression=expression):
                # Parentheses do not add AST depth and are intentionally valid within length bound.
                if expression.startswith("("*100):
                    self.assertEqual(calculate(expression), "1")
                else:
                    with self.assertRaises(ValueError): calculate(expression)

    def test_depth_bound(self):
        with self.assertRaises(ValueError): calculate("-"*20 + "1")

    def test_unknown_operation(self):
        with self.assertRaises(ValueError): Calculator().handle("evil", {"expression": "1"})

if __name__ == "__main__": unittest.main()
