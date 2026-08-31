"""LLM adapter for listing available Google calendars."""
# ruff: noqa: D101, D102

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.google_calendar import CalendarError, list_calendars
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class ListCalendars(Tool):
    name = "list_calendars"
    description = "List available Google calendars and their names, IDs, primary status, and access roles."
    parameters_schema = {"type": "object", "properties": {}}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        try:
            calendars = list_calendars(instance_path=deps.instance_path)
        except CalendarError as exc:
            logger.warning("list_calendars failed: %s", exc)
            return {"error": str(exc)}
        return {"calendars": calendars}
