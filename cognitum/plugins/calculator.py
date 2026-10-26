"""Safe to delete. System continues with reduced capability.

Bounded arithmetic grammar; no eval, imports, calls, variables or attributes.
Decimal literal text is interpreted as an exact rational, not binary float.
"""
import ast
from fractions import Fraction
from ..contracts import Manifest, Operation, Shape

def calculate(expression):
    if type(expression) is not str or not 1 <= len(expression) <= 256:
        raise ValueError("expression length")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as error:
        raise ValueError("invalid expression") from error
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("too many nodes")

    def visit(node, depth=0):
        if depth > 16:
            raise ValueError("depth limit")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            token = ast.get_source_segment(expression, node)
            # Bound exponent notation before constructing Fraction.
            if len(token) > 40 or "e" in token.lower() or "x" in token.lower() or "_" in token:
                raise ValueError("unsupported numeric literal")
            value = Fraction(token)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand, depth + 1)
            if isinstance(node.op, ast.USub):
                value = -value
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            elif isinstance(node.op, ast.Div):
                if not right: raise ValueError("division by zero")
                value = left / right
            else:
                if right.denominator != 1 or abs(right) > 16 or (not left and right < 0):
                    raise ValueError("exponent limit")
                value = left ** int(right)
        else:
            raise ValueError("unsupported syntax")
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 1024:
            raise ValueError("magnitude limit")
        return value
    return str(visit(tree.body))

class Calculator:
    def manifest(self):
        return Manifest("reference_calc", "0.1.0", (Operation(
            "calc.rational", "calc", Shape((("expression", 256),)), Shape((("value", 1024),)),
            assurance="exact_arithmetic"),))

    def health(self): return True

    def self_test(self):
        return calculate("0.1 + 0.2") == "3/10" and calculate("1/3*3") == "1"

    def handle(self, operation, payload):
        if operation != "calc.rational": raise ValueError("unknown operation")
        return {"value": calculate(payload["expression"])}
