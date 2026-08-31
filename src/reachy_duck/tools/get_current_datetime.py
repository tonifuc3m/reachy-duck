"""LLM adapter for fresh local system time."""

from __future__ import annotations
from typing import Any

from reachy_duck.time_context import current_datetime_payload
from reachy_duck.tools.core_tools import Tool, ToolDependencies


class GetCurrentDatetime(Tool):
    """Return fresh timezone-aware local temporal context."""

    name = "get_current_datetime"
    description = (
        "Get the current local date and time from Reachy's system clock. Use for fresh time-sensitive context."
    )
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, str]:
        """Return a concise ISO-8601 representation of the current local time."""
        return current_datetime_payload()
