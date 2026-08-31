"""LLM adapter for safely updating Google Calendar events."""
# ruff: noqa: D101, D102

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.google_calendar import CalendarError, update_calendar_event
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class UpdateCalendarEvent(Tool):
    name = "update_calendar_event"
    description = (
        "Update one unambiguously identified Google Calendar event; require a recurrence scope for an occurrence."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "match_title": {"type": "string"},
            "match_start": {"type": "string"},
            "match_end": {"type": "string"},
            "calendar": {"type": "string"},
            "target_calendar": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "clear_description": {"type": "boolean"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "attendees": {"type": "array", "items": {"type": "string", "format": "email"}},
            "attendee_action": {"type": "string", "enum": ["replace", "add"]},
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
            "clear_color": {"type": "boolean"},
            "recurrence": {
                "type": "object",
                "properties": {
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly", "yearly"]},
                    "weekdays": {"type": "array", "items": {"type": "string"}},
                    "until": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                },
                "required": ["frequency"],
            },
            "clear_recurrence": {"type": "boolean"},
            "recurrence_scope": {"type": "string", "enum": ["this", "all", "future"]},
            "reminders": {"type": "array", "maxItems": 5, "items": {"type": "object"}},
            "create_google_meet": {"type": "boolean"},
            "timezone": {"type": "string"},
        },
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        try:
            event = update_calendar_event(instance_path=deps.instance_path, **kwargs)
        except CalendarError as exc:
            logger.warning("update_calendar_event failed: %s", exc)
            return {"error": str(exc)}
        return {"event": event}
