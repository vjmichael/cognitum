"""C05 P2.1: independent exact-math invariants for inert Protobuf specialists.

These tests do not authorize Lu registration or claim model efficacy.
They compare the production elimination/bisection implementations against
independently constructed exact rational mathematical identities.
"""
import itertools
from fractions import Fraction
import unittest

from cognitum.proto import specialists_pb2 as pb
from cognitum.scientific_math import run_inert_specialist, decode_specialist_result, _wire


def call(kind, request):
    return decode_specialist_result(kind, run_inert_specialist(kind, _wire(request)))


def matrix_request(action, a, b=()):
    request = pb.LinearRequest(action=action)
    for row in a:
        request.a.add(entries=[str(value) for value in row])
    for row in b:
        request.b.add(entries=[str(value) for value in row])
    return request


def permutation_determinant(matrix):
    """Leibniz expansion: independent of the production elimination algorithm."""
    n = len(matrix)
    total = Fraction(0)
    for perm in itertools.permutations(range(n)):
        inversions = sum(perm[i] > perm[j] for i in range(n) for j in range(i + 1, n))
        term = Fraction(-1 if inversions % 2 else 1)
        for row, col in enumerate(perm):
            term *= matrix[row][col]
        total += term
    return total


def horner(coefficients, x):
    """Independent direct polynomial evaluation; coefficients highest degree first."""
    value = Fraction(0)
    for coefficient in coefficients:
        value = value * x + coefficient
    return value


class C05IndependentInvariants(unittest.TestCase):
    def test_determinants_against_leibniz_and_row_swap_sign(self):
        for matrix in (
            [[Fraction(7)]],
            [[Fraction(2), Fraction(3)], [Fraction(5), Fraction(11)]],
            [[Fraction(1, 2), Fraction(2), Fraction(-1)],
             [Fraction(0), Fraction(3), Fraction(4)],
             [Fraction(5), Fraction(1, 3), Fraction(2)]],
            [[Fraction(2), Fraction(0), Fraction(1), Fraction(3)],
             [Fraction(1), Fraction(4), Fraction(0), Fraction(1)],
             [Fraction(0), Fraction(2), Fraction(5), Fraction(-1)],
             [Fraction(3), Fraction(1), Fraction(2), Fraction(6)]],
        ):
            with self.subTest(matrix=matrix):
                result = call("linear", matrix_request("determinant", matrix))
                self.assertEqual(Fraction(result.scalar), permutation_determinant(matrix))
                if len(matrix) >= 2:
                    swapped = [row[:] for row in matrix]
                    swapped[0], swapped[1] = swapped[1], swapped[0]
                    other = call("linear", matrix_request("determinant", swapped))
                    self.assertEqual(Fraction(other.scalar), -Fraction(result.scalar))

    def test_linear_solve_exact_residual_not_merely_expected_answer(self):
        cases = (
            ([[Fraction(2), Fraction(1)], [Fraction(1), Fraction(3)]],
             [Fraction(1), Fraction(2)]),
            ([[Fraction(1, 2), Fraction(2), Fraction(0)],
              [Fraction(1), Fraction(1), Fraction(1)],
              [Fraction(0), Fraction(1), Fraction(2)]],
             [Fraction(1), Fraction(0), Fraction(4)]),
            ([[Fraction(3)]], [Fraction(1, 7)]),
        )
        for matrix, rhs in cases:
            with self.subTest(matrix=matrix):
                result = call("linear", matrix_request("solve", matrix, [[v] for v in rhs]))
                solution = [Fraction(row.entries[0]) for row in result.rows]
                self.assertEqual(len(solution), len(rhs))
                for row, expected in zip(matrix, rhs):
                    self.assertEqual(sum((a*x for a, x in zip(row, solution)), Fraction(0)), expected)

    def test_root_interval_sign_witness_and_nesting(self):
        cases = (
            ("x**2-2", [1, 0, -2], Fraction(1), Fraction(2)),
            ("x**3-x-1", [1, 0, -1, -1], Fraction(1), Fraction(2)),
            ("x**2-3", [1, 0, -3], Fraction(-2), Fraction(-1)),
        )
        for expression, coefficients, lo, hi in cases:
            with self.subTest(expression=expression):
                prior_width = hi - lo
                for steps in (1, 8, 32, 64):
                    result = call("root", pb.RootRequest(
                        polynomial=expression, lower=str(lo), upper=str(hi),
                        iterations=steps))
                    left, right = Fraction(result.lower), Fraction(result.upper)
                    self.assertLessEqual(lo, left)
                    self.assertLessEqual(right, hi)
                    self.assertLessEqual(left, right)
                    self.assertLessEqual(right-left, prior_width / (2**steps))
                    f_left, f_right = horner(coefficients, left), horner(coefficients, right)
                    self.assertTrue(f_left == 0 or f_right == 0 or
                                    (f_left < 0 < f_right) or (f_right < 0 < f_left))
                    self.assertEqual(Fraction(result.midpoint), (left+right)/2)

    def test_singular_system_never_yields_fabricated_solution(self):
        matrix = [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]
        with self.assertRaises(ValueError):
            call("linear", matrix_request("solve", matrix, [[1], [3]]))


if __name__ == "__main__":
    unittest.main()
