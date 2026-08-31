"""LLM adapter for reading Google Calendar events."""

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.google_calendar import CalendarError, list_calendar_events
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class ListCalendarEvents(Tool):
    """List explicitly bounded Google Calendar events."""

    name = "list_calendar_events"
    description = (
        "List the user's Google Calendar events in a requested unambiguous interval. "
        "Datetimes must be ISO-8601 and include a UTC offset."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "start": {"type": "string", "description": "ISO-8601 interval start with UTC offset."},
            "end": {"type": "string", "description": "ISO-8601 interval end with UTC offset."},
            "calendar": {"type": "string", "description": "Calendar ID or exact name; defaults to primary."},
            "timezone": {"type": "string", "description": "Optional IANA timezone, e.g. Europe/Madrid."},
        },
        "required": ["start", "end"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """List events, returning expected failures to the conversation loop."""
        try:
            events = list_calendar_events(
                start=str(kwargs.get("start", "")),
                end=str(kwargs.get("end", "")),
                calendar=kwargs.get("calendar"),
                timezone_name=kwargs.get("timezone"),
                instance_path=deps.instance_path,
            )
        except CalendarError as exc:
            logger.warning("list_calendar_events failed: %s", exc)
            return {"error": str(exc)}
        return {"events": events}
