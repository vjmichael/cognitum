"""C05 AST-independent reference PARSER for differential math tests.

This is a checked, bounded educational/reference interpreter: no eval, no
Python AST, no model calls, no Lu tool registration, no resource grants.
It shares stdlib fractions.Fraction as the arithmetic primitive with the
production parser, so matching it is NOT a formal correctness certificate.
"""
from fractions import Fraction
import re

_TOK = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+|\*\*|[()+\-*/])")


def reference_calculate(expression):
    """Verify the same deliberately narrow arithmetic subset independently."""
    if type(expression) is not str or not 1 <= len(expression) <= 256:
        raise ValueError("reference expression length")
    tokens = []
    pos = 0
    while pos < len(expression):
        if expression[pos] in " \t":
            pos += 1
            continue
        match = _TOK.match(expression, pos)
        if match is None:
            raise ValueError("unsupported reference character")
        tokens.append(match.group())
        if len(tokens) > 64:
            raise ValueError("reference token bound")
        pos = match.end()
    if not tokens:
        raise ValueError("empty reference expression")
    cursor = 0

    def peek():
        return tokens[cursor] if cursor < len(tokens) else ""

    def take(expected):
        nonlocal cursor
        if peek() != expected:
            raise ValueError("invalid reference grammar")
        cursor += 1

    def bounded(value):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 1024:
            raise ValueError("reference magnitude bound")
        return value

    def additive(depth):
        nonlocal cursor
        left = multiplicative(depth)
        while peek() in ("+", "-"):
            op = peek()
            cursor += 1
            right = multiplicative(depth)
            left = bounded(left + right if op == "+" else left - right)
        return left

    def multiplicative(depth):
        nonlocal cursor
        left = signed(depth)
        while peek() in ("*", "/"):
            op = peek()
            cursor += 1
            right = signed(depth)
            if op == "/" and not right:
                raise ValueError("division by zero")
            left = bounded(left * right if op == "*" else left / right)
        return left

    def signed(depth):
        nonlocal cursor
        if depth > 16:
            raise ValueError("reference depth bound")
        if peek() in ("+", "-"):
            op = peek()
            cursor += 1
            value = signed(depth + 1)
            return bounded(-value if op == "-" else value)
        return exponent(depth)

    def exponent(depth):
        nonlocal cursor
        base = atom(depth)
        if peek() == "**":
            cursor += 1
            power = signed(depth + 1)  # right-associative, signed exponent
            if power.denominator != 1 or abs(power) > 16 or (not base and power < 0):
                raise ValueError("reference exponent bound")
            base = bounded(base ** int(power))
        return base

    def atom(depth):
        nonlocal cursor
        if depth > 16:
            raise ValueError("reference nesting bound")
        token = peek()
        if token == "(":
            cursor += 1
            value = additive(depth + 1)
            take(")")
            return value
        if not token or not (token[0].isdigit() or token[0] == "."):
            raise ValueError("missing reference operand")
        if len(token) > 40:
            raise ValueError("reference literal bound")
        cursor += 1
        return bounded(Fraction(token))

    result = additive(0)
    if cursor != len(tokens):
        raise ValueError("trailing reference tokens")
    return str(result)
