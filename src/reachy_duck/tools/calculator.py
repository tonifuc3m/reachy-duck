"""LLM adapter for the restricted arithmetic calculator."""

from typing import Any

from reachy_duck.calculator import calculate
from reachy_duck.tools.core_tools import Tool, ToolDependencies


class Calculator(Tool):
    """Evaluate a simple arithmetic expression."""

    name = "calculator"
    description = "Calculate a simple arithmetic expression using +, -, *, /, %, **, parentheses, and decimals."
    parameters_schema = {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "Arithmetic expression to calculate."}},
        "required": ["expression"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return the calculator result or a concise error."""
        expression = kwargs.get("expression")
        if not isinstance(expression, str):
            return {"expression": str(expression), "error": "Expression must be a string"}
        return calculate(expression)
