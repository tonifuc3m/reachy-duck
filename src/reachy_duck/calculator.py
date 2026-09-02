"""Small, safe arithmetic expression evaluator."""

from __future__ import annotations
import ast
import math
from typing import Any


MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 100
MAX_NUMERIC_MAGNITUDE = 1_000_000_000_000


class CalculatorError(ValueError):
    """A user-facing calculator error."""


def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a restricted arithmetic expression without executing Python code."""
    if not isinstance(expression, str):
        return {"expression": str(expression), "error": "Expression must be a string"}

    normalized = expression.strip()
    if not normalized:
        return {"expression": expression, "error": "Expression is empty"}
    if len(normalized) > MAX_EXPRESSION_LENGTH:
        return {"expression": expression, "error": "Expression exceeds maximum length"}

    try:
        tree = ast.parse(normalized, mode="eval")
        result = _evaluate(tree.body)
    except CalculatorError as exc:
        return {"expression": expression, "error": str(exc)}
    except (SyntaxError, ValueError, OverflowError):
        return {"expression": expression, "error": "Malformed expression"}

    return {"expression": expression, "result": _display_number(result)}


def _evaluate(node: ast.expr) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return _checked_number(node.value)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate(node.operand)
        return _checked_number(operand if isinstance(node.op, ast.UAdd) else -operand)

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return _checked_number(left + right)
        if isinstance(node.op, ast.Sub):
            return _checked_number(left - right)
        if isinstance(node.op, ast.Mult):
            return _checked_number(left * right)
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise CalculatorError("Division by zero")
            return _checked_number(left / right)
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise CalculatorError("Division by zero")
            return _checked_number(left % right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT:
                raise CalculatorError("Exponent exceeds maximum size")
            try:
                return _checked_number(left**right)
            except ZeroDivisionError as exc:
                raise CalculatorError("Division by zero") from exc

    raise CalculatorError("Unsupported expression")


def _checked_number(value: int | float) -> int | float:
    if isinstance(value, complex) or not math.isfinite(value):
        raise CalculatorError("Numeric magnitude exceeds maximum")
    if abs(value) > MAX_NUMERIC_MAGNITUDE:
        raise CalculatorError("Numeric magnitude exceeds maximum")
    return value


def _display_number(value: int | float) -> int | float:
    """Keep integral float results concise in JSON responses."""
    return int(value) if isinstance(value, float) and value.is_integer() else value
