"""LLM adapter for creating Google Calendar events."""

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.google_calendar import CalendarError, create_calendar_event
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class CreateCalendarEvent(Tool):
    """Create one explicitly scheduled Google Calendar event."""

    name = "create_calendar_event"
    description = (
        "Create an event in the user's Google Calendar only after the title and an unambiguous date and time are known. "
        "Datetimes must be ISO-8601 and include a UTC offset, for example 2026-09-01T19:00:00+02:00."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short event title."},
            "start": {"type": "string", "description": "ISO-8601 start datetime with UTC offset."},
            "end": {"type": "string", "description": "Optional ISO-8601 end datetime with UTC offset."},
            "description": {"type": "string", "description": "Optional event description."},
            "attendees": {
                "type": "array",
                "items": {"type": "string", "format": "email"},
                "description": "Email addresses to invite; invitations are sent to all listed addresses.",
            },
            "color": {
                "type": "string",
                "enum": [
                    "lavender",
                    "sage",
                    "grape",
                    "flamingo",
                    "banana",
                    "tangerine",
                    "peacock",
                    "graphite",
                    "blueberry",
                    "basil",
                    "tomato",
                    "red",
                    "green",
                    "blue",
                ],
            },
            "recurrence": {
                "type": "object",
                "properties": {
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly", "yearly"]},
                    "weekdays": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                        },
                    },
                    "until": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                },
                "required": ["frequency"],
            },
            "reminders": {"type": "array", "maxItems": 5, "items": {"type": "object"}},
            "create_google_meet": {"type": "boolean"},
            "calendar": {
                "type": "string",
                "description": "Calendar ID or exact human-readable calendar name; defaults to primary.",
            },
            "timezone": {"type": "string", "description": "Optional IANA timezone, e.g. Europe/Madrid."},
        },
        "required": ["title", "start"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Create the event, returning expected failures to the conversation loop."""
        try:
            event = create_calendar_event(
                title=str(kwargs.get("title", "")),
                start=str(kwargs.get("start", "")),
                end=kwargs.get("end"),
                description=kwargs.get("description"),
                attendees=kwargs.get("attendees"),
                color=kwargs.get("color"),
                recurrence=kwargs.get("recurrence"),
                reminders=kwargs.get("reminders"),
                create_google_meet=bool(kwargs.get("create_google_meet", False)),
                calendar=kwargs.get("calendar"),
                timezone_name=kwargs.get("timezone"),
                instance_path=deps.instance_path,
            )
        except CalendarError as exc:
            logger.warning("create_calendar_event failed: %s", exc)
            return {"error": str(exc)}
        return {"event": event}
