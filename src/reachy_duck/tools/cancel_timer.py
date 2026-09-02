"""LLM adapter for cancelling a local timer."""

from __future__ import annotations
from typing import Any

from reachy_duck.tools.core_tools import Tool, ToolDependencies


class CancelTimer(Tool):
    """Cancel one active local timer by identifier."""

    name = "cancel_timer"
    description = "Cancel one active local timer by its id. List timers first when selecting by label."
    parameters_schema = {
        "type": "object",
        "properties": {"timer_id": {"type": "string", "description": "The timer id returned by list_timers."}},
        "required": ["timer_id"],
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, object]:
        """Cancel a timer while preserving clear expected failures."""
        if deps.timer_manager is None:
            return {"error": "local timers are unavailable"}
        timer_id = kwargs.get("timer_id")
        if not isinstance(timer_id, str) or not timer_id.strip():
            return {"error": "timer_id must be a non-empty string"}
        return deps.timer_manager.cancel_timer(timer_id)
