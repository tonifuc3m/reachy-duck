"""LLM adapter for listing local timers."""

from __future__ import annotations
from typing import Any

from reachy_duck.tools.core_tools import Tool, ToolDependencies


class ListTimers(Tool):
    """List active local timers."""

    name = "list_timers"
    description = "List active local timers and any expired timers that have not yet been announced."
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, object]:
        """Return timers without changing them."""
        if deps.timer_manager is None:
            return {"error": "local timers are unavailable"}
        return {"timers": deps.timer_manager.list_timers()}
