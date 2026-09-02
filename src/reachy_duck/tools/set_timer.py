"""LLM adapter for creating a local relative timer."""

from __future__ import annotations
from typing import Any

from reachy_duck.tools.core_tools import Tool, ToolDependencies


class SetTimer(Tool):
    """Create a local, process-lifetime relative timer."""

    name = "set_timer"
    description = "Set a local relative timer for a positive number of seconds. It is lost if Reachy Duck restarts."
    parameters_schema = {
        "type": "object",
        "properties": {
            "duration_seconds": {"type": "number", "description": "Positive relative duration in seconds."},
            "label": {"type": ["string", "null"], "description": "Optional short label, such as 'pasta'."},
        },
        "required": ["duration_seconds"],
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, object]:
        """Schedule the timer without waiting for its duration."""
        if deps.timer_manager is None:
            return {"error": "local timers are unavailable"}
        duration_seconds = kwargs.get("duration_seconds")
        if not isinstance(duration_seconds, (int, float)) or isinstance(duration_seconds, bool):
            return {"error": "duration_seconds must be a positive number"}
        label = kwargs.get("label")
        if label is not None and not isinstance(label, str):
            return {"error": "label must be a string or null"}
        try:
            return deps.timer_manager.set_timer(float(duration_seconds), label)
        except ValueError as exc:
            return {"error": str(exc)}
