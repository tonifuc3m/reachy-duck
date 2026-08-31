"""Google Calendar persistence and API access, independent of Reachy hardware."""
# ruff: noqa: D101, D102, D103

from __future__ import annotations
import logging
from uuid import uuid4
from typing import Any, Literal, Protocol, cast
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from reachy_duck.memory import persistent_data_directory
from reachy_duck.time_context import TimeContextError, current_timezone


logger = logging.getLogger(__name__)
GOOGLE_DIRECTORY_NAME = "google"
CLIENT_SECRET_FILENAME = "client_secret.json"
TOKEN_FILENAME = "token.json"
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]
DEFAULT_EVENT_DURATION = timedelta(minutes=30)
EVENT_COLORS = {
    "lavender": "1",
    "sage": "2",
    "grape": "3",
    "flamingo": "4",
    "banana": "5",
    "tangerine": "6",
    "peacock": "7",
    "graphite": "8",
    "blueberry": "9",
    "basil": "10",
    "tomato": "11",
    "red": "11",
    "green": "10",
    "blue": "9",
}
RecurrenceScope = Literal["this", "all", "future"]


class CalendarService(Protocol):
    def events(self) -> Any: ...
    def calendarList(self) -> Any: ...


class CalendarError(RuntimeError):
    """Expected local authentication or Calendar API failure."""


def google_directory_for_instance(instance_path: str | Path | None = None) -> Path:
    root = Path(instance_path).expanduser() if instance_path is not None else persistent_data_directory().parent
    return root / GOOGLE_DIRECTORY_NAME


def client_secret_path_for_instance(instance_path: str | Path | None = None) -> Path:
    return google_directory_for_instance(instance_path) / CLIENT_SECRET_FILENAME


def token_path_for_instance(instance_path: str | Path | None = None) -> Path:
    return google_directory_for_instance(instance_path) / TOKEN_FILENAME


def resolve_timezone(timezone_name: str | None = None) -> ZoneInfo:
    try:
        return current_timezone(timezone_name)
    except TimeContextError as exc:
        raise CalendarError(str(exc)) from exc


def parse_aware_datetime(value: str, *, timezone: ZoneInfo) -> datetime:
    if not isinstance(value, str):
        raise CalendarError("datetime must be an ISO-8601 string with a UTC offset")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarError("datetime must be ISO-8601 with a UTC offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarError("datetime must include a UTC offset or timezone")
    return parsed.astimezone(timezone)


def _write_private_token(credentials: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    path.chmod(0o600)


def authorize_google_calendar(*, instance_path: str | Path | None = None, port: int = 8080) -> Path:
    if not 1 <= port <= 65535:
        raise CalendarError("OAuth port must be between 1 and 65535")
    client_path = client_secret_path_for_instance(instance_path)
    if not client_path.is_file():
        raise CalendarError(f"OAuth client file not found: {client_path}")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), CALENDAR_SCOPES)
        credentials = flow.run_local_server(host="127.0.0.1", port=port, open_browser=False)
        path = token_path_for_instance(instance_path)
        _write_private_token(credentials, path)
        return path
    except ImportError as exc:
        raise CalendarError("Google Calendar dependencies are not installed") from exc
    except OSError as exc:
        raise CalendarError(f"OAuth authorization failed: {exc}") from exc


def build_calendar_service(*, instance_path: str | Path | None = None) -> CalendarService:
    path = token_path_for_instance(instance_path)
    if not path.is_file():
        raise CalendarError("Google Calendar is not connected; run reachy-duck google-auth first")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request

        credentials = Credentials.from_authorized_user_file(str(path), CALENDAR_SCOPES)  # type: ignore[no-untyped-call]
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CalendarError("Google Calendar authorization expired; run reachy-duck google-auth again")
            credentials.refresh(Request())
            _write_private_token(credentials, path)
        return cast(CalendarService, build("calendar", "v3", credentials=credentials, cache_discovery=False))
    except CalendarError:
        raise
    except ImportError as exc:
        raise CalendarError("Google Calendar dependencies are not installed") from exc
    except Exception as exc:
        logger.warning("Failed to initialize Google Calendar client: %s", exc)
        raise CalendarError(f"Google Calendar authentication failed: {exc}") from exc


def _service(service: CalendarService | None, instance_path: str | Path | None) -> CalendarService:
    return service or build_calendar_service(instance_path=instance_path)


def list_calendars(
    *, service: CalendarService | None = None, instance_path: str | Path | None = None
) -> list[dict[str, str | bool]]:
    try:
        response = _service(service, instance_path).calendarList().list().execute()
    except Exception as exc:
        logger.warning("Failed to list Google calendars: %s", exc)
        raise CalendarError(f"failed to list calendars: {exc}") from exc
    return [
        {
            "name": str(item.get("summaryOverride") or item.get("summary", "Untitled calendar")),
            "id": str(item["id"]),
            "primary": bool(item.get("primary", False)),
            "access_role": str(item.get("accessRole", "unknown")),
        }
        for item in response.get("items", [])
        if not item.get("deleted") and item.get("id")
    ]


def resolve_calendar_id(
    calendar: str | None, *, service: CalendarService | None = None, instance_path: str | Path | None = None
) -> str:
    if calendar is None or not calendar.strip() or calendar.strip() == "primary":
        return "primary"
    requested = calendar.strip()
    calendars = list_calendars(service=service, instance_path=instance_path)
    matches = [entry for entry in calendars if entry["id"] == requested] or [
        entry for entry in calendars if str(entry["name"]).casefold() == requested.casefold()
    ]
    if not matches:
        raise CalendarError(f"calendar not found: {requested}")
    if len(matches) > 1:
        raise CalendarError(f"multiple calendars match {requested}; ask which one to use")
    return str(matches[0]["id"])


def recurrence_rule(
    *,
    frequency: str,
    weekdays: list[str] | None = None,
    until: str | None = None,
    count: int | None = None,
    timezone: ZoneInfo,
) -> str:
    frequencies = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY", "yearly": "YEARLY"}
    if frequency not in frequencies:
        raise CalendarError("recurrence frequency must be daily, weekly, monthly, or yearly")
    if until is not None and count is not None:
        raise CalendarError("recurrence can end with either until or count, not both")
    parts = [f"FREQ={frequencies[frequency]}"]
    if weekdays:
        codes_by_day = {
            "monday": "MO",
            "tuesday": "TU",
            "wednesday": "WE",
            "thursday": "TH",
            "friday": "FR",
            "saturday": "SA",
            "sunday": "SU",
        }
        try:
            codes = [codes_by_day[day.casefold()] for day in weekdays]
        except (AttributeError, KeyError) as exc:
            raise CalendarError("recurrence weekdays must be full weekday names") from exc
        if frequency != "weekly":
            raise CalendarError("recurrence weekdays require weekly frequency")
        parts.append(f"BYDAY={','.join(codes)}")
    if until:
        parts.append(
            f"UNTIL={parse_aware_datetime(until, timezone=timezone).astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}"
        )
    if count is not None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise CalendarError("recurrence count must be a positive integer")
        parts.append(f"COUNT={count}")
    return "RRULE:" + ";".join(parts)


def _color_id(color: str | None) -> str | None:
    if color is None:
        return None
    if not isinstance(color, str) or color.casefold().strip() not in EVENT_COLORS:
        raise CalendarError(f"unsupported color: {color}. Choose from {', '.join(sorted(EVENT_COLORS))}")
    return EVENT_COLORS[color.casefold().strip()]


def _attendees(emails: list[str] | None) -> list[dict[str, str]] | None:
    if emails is None:
        return None
    if not all(isinstance(email, str) and "@" in email and email.strip().count("@") == 1 for email in emails):
        raise CalendarError("attendees must be email addresses; ask for an email address rather than guessing")
    return [{"email": email.strip()} for email in emails]


def _reminders(reminders: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if reminders is None:
        return None
    if len(reminders) > 5 or any(
        r.get("method") not in {"email", "popup"} or not isinstance(r.get("minutes"), int) or r["minutes"] < 0
        for r in reminders
    ):
        raise CalendarError("reminders must contain at most five email or popup reminders with non-negative minutes")
    return {"useDefault": False, "overrides": reminders}


def _event_body(
    *,
    title: str,
    start_at: datetime,
    end_at: datetime,
    timezone: ZoneInfo,
    description: str | None = None,
    attendees: list[str] | None = None,
    color: str | None = None,
    recurrence: dict[str, Any] | None = None,
    reminders: list[dict[str, Any]] | None = None,
    create_google_meet: bool = False,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": title.strip(),
        "start": {"dateTime": start_at.isoformat(), "timeZone": timezone.key},
        "end": {"dateTime": end_at.isoformat(), "timeZone": timezone.key},
    }
    if description is not None:
        body["description"] = description.strip()
    parsed_attendees = _attendees(attendees)
    if parsed_attendees is not None:
        body["attendees"] = parsed_attendees
    if (color_id := _color_id(color)) is not None:
        body["colorId"] = color_id
    if recurrence is not None:
        body["recurrence"] = [recurrence_rule(timezone=timezone, **recurrence)]
    parsed_reminders = _reminders(reminders)
    if parsed_reminders is not None:
        body["reminders"] = parsed_reminders
    if create_google_meet:
        body["conferenceData"] = {"createRequest": {"requestId": str(uuid4())}}
    return body


def _result(event: dict[str, Any], fallback: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(event.get("id", fallback.get("id", ""))),
        "title": str(event.get("summary", fallback.get("summary", "Untitled event"))),
        "start": str(event.get("start", fallback.get("start", {})).get("dateTime", "")),
        "end": str(event.get("end", fallback.get("end", {})).get("dateTime", "")),
    }


def create_calendar_event(
    *,
    title: str,
    start: str,
    end: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    color: str | None = None,
    recurrence: dict[str, Any] | None = None,
    reminders: list[dict[str, Any]] | None = None,
    create_google_meet: bool = False,
    calendar: str | None = None,
    timezone_name: str | None = None,
    service: CalendarService | None = None,
    instance_path: str | Path | None = None,
) -> dict[str, str]:
    if not isinstance(title, str) or not title.strip():
        raise CalendarError("title must be a non-empty string")
    timezone = resolve_timezone(timezone_name)
    start_at = parse_aware_datetime(start, timezone=timezone)
    end_at = parse_aware_datetime(end, timezone=timezone) if end else start_at + DEFAULT_EVENT_DURATION
    if end_at <= start_at:
        raise CalendarError("end datetime must be after start datetime")
    active_service = _service(service, instance_path)
    body = _event_body(
        title=title,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
        description=description,
        attendees=attendees,
        color=color,
        recurrence=recurrence,
        reminders=reminders,
        create_google_meet=create_google_meet,
    )
    kwargs: dict[str, Any] = {"calendarId": resolve_calendar_id(calendar, service=active_service), "body": body}
    if attendees:
        kwargs["sendUpdates"] = "all"
    if create_google_meet:
        kwargs["conferenceDataVersion"] = 1
    try:
        event = active_service.events().insert(**kwargs).execute()
    except Exception as exc:
        logger.warning("Failed to create Google Calendar event: %s", exc)
        raise CalendarError(f"failed to create calendar event: {exc}") from exc
    return _result(event, body)


def _format_event_time(event_time: dict[str, str], timezone: ZoneInfo) -> str:
    if "date" in event_time:
        return f"all day {event_time['date']}"
    value = event_time.get("dateTime")
    return parse_aware_datetime(value, timezone=timezone).strftime("%a %d %b, %H:%M") if value else "unscheduled"


def list_calendar_events(
    *,
    start: str,
    end: str,
    calendar: str | None = None,
    timezone_name: str | None = None,
    service: CalendarService | None = None,
    instance_path: str | Path | None = None,
) -> list[dict[str, str]]:
    timezone = resolve_timezone(timezone_name)
    start_at = parse_aware_datetime(start, timezone=timezone)
    end_at = parse_aware_datetime(end, timezone=timezone)
    if end_at <= start_at:
        raise CalendarError("end datetime must be after start datetime")
    active_service = _service(service, instance_path)
    try:
        response = (
            active_service.events()
            .list(
                calendarId=resolve_calendar_id(calendar, service=active_service),
                timeMin=start_at.isoformat(),
                timeMax=end_at.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to list Google Calendar events: %s", exc)
        raise CalendarError(f"failed to list calendar events: {exc}") from exc
    return [
        {
            "id": str(event.get("id", "")),
            "title": str(event.get("summary", "Untitled event")),
            "start": _format_event_time(event.get("start", {}), timezone),
            "end": _format_event_time(event.get("end", {}), timezone),
            "recurring_event_id": str(event.get("recurringEventId", "")),
        }
        for event in response.get("items", [])
        if event.get("status") != "cancelled"
    ]


def _find_event(
    *, title: str, start: str, end: str, calendar_id: str, timezone: ZoneInfo, service: CalendarService
) -> dict[str, Any]:
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=parse_aware_datetime(start, timezone=timezone).isoformat(),
            timeMax=parse_aware_datetime(end, timezone=timezone).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    matches = [
        event
        for event in response.get("items", [])
        if event.get("status") != "cancelled" and str(event.get("summary", "")).casefold() == title.casefold()
    ]
    if not matches:
        raise CalendarError(f"no event named {title} matches that time")
    if len(matches) > 1:
        raise CalendarError(f"multiple events named {title} match; ask which one to update")
    return cast(dict[str, Any], matches[0])


def update_calendar_event(
    *,
    event_id: str | None = None,
    match_title: str | None = None,
    match_start: str | None = None,
    match_end: str | None = None,
    calendar: str | None = None,
    target_calendar: str | None = None,
    title: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    start: str | None = None,
    end: str | None = None,
    attendees: list[str] | None = None,
    attendee_action: Literal["replace", "add"] = "replace",
    color: str | None = None,
    clear_color: bool = False,
    recurrence: dict[str, Any] | None = None,
    clear_recurrence: bool = False,
    recurrence_scope: RecurrenceScope | None = None,
    reminders: list[dict[str, Any]] | None = None,
    create_google_meet: bool = False,
    timezone_name: str | None = None,
    service: CalendarService | None = None,
    instance_path: str | Path | None = None,
) -> dict[str, str]:
    timezone = resolve_timezone(timezone_name)
    active_service = _service(service, instance_path)
    calendar_id = resolve_calendar_id(calendar, service=active_service)
    try:
        if event_id:
            event = active_service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        elif match_title and match_start and match_end:
            event = _find_event(
                title=match_title,
                start=match_start,
                end=match_end,
                calendar_id=calendar_id,
                timezone=timezone,
                service=active_service,
            )
        else:
            raise CalendarError("provide an event ID or a title and precise time range to identify one event")
        is_instance = bool(event.get("recurringEventId"))
        if is_instance and recurrence_scope is None:
            raise CalendarError("is this occurrence only or the entire recurring series?")
        if recurrence_scope == "future":
            raise CalendarError("updating this and future recurring events is not supported safely")
        if is_instance and recurrence_scope == "all":
            event = active_service.events().get(calendarId=calendar_id, eventId=event["recurringEventId"]).execute()
        if description is not None and clear_description:
            raise CalendarError("description cannot be both changed and cleared")
        if description is not None:
            event["description"] = description.strip()
        elif clear_description:
            event["description"] = ""
        if title is not None:
            event["summary"] = title.strip()
        if start is not None:
            start_at = parse_aware_datetime(start, timezone=timezone)
            event["start"] = {"dateTime": start_at.isoformat(), "timeZone": timezone.key}
            if end is None:
                end = (start_at + DEFAULT_EVENT_DURATION).isoformat()
        if end is not None:
            event["end"] = {
                "dateTime": parse_aware_datetime(end, timezone=timezone).isoformat(),
                "timeZone": timezone.key,
            }
        if attendees is not None:
            new_attendees = _attendees(attendees) or []
            if attendee_action == "add":
                existing = {str(item.get("email", "")).casefold() for item in event.get("attendees", [])}
                event["attendees"] = event.get("attendees", []) + [
                    item for item in new_attendees if item["email"].casefold() not in existing
                ]
            elif attendee_action == "replace":
                event["attendees"] = new_attendees
            else:
                raise CalendarError("attendee_action must be replace or add")
        if color is not None and clear_color:
            raise CalendarError("color cannot be both changed and cleared")
        if color is not None:
            event["colorId"] = _color_id(color)
        elif clear_color:
            event.pop("colorId", None)
        if recurrence is not None and clear_recurrence:
            raise CalendarError("recurrence cannot be both changed and cleared")
        if recurrence is not None:
            event["recurrence"] = [recurrence_rule(timezone=timezone, **recurrence)]
        elif clear_recurrence:
            event.pop("recurrence", None)
        if reminders is not None:
            event["reminders"] = _reminders(reminders)
        if create_google_meet:
            event["conferenceData"] = {"createRequest": {"requestId": str(uuid4())}}
        update_kwargs: dict[str, Any] = {"calendarId": calendar_id, "eventId": event["id"], "body": event}
        if attendees is not None:
            update_kwargs["sendUpdates"] = "all"
        if create_google_meet:
            update_kwargs["conferenceDataVersion"] = 1
        updated = active_service.events().update(**update_kwargs).execute()
        if target_calendar is not None:
            destination = resolve_calendar_id(target_calendar, service=active_service)
            if destination != calendar_id:
                updated = (
                    active_service.events()
                    .move(
                        calendarId=calendar_id,
                        eventId=updated["id"],
                        destination=destination,
                        sendUpdates="all" if attendees is not None else "none",
                    )
                    .execute()
                )
        return _result(updated, event)
    except CalendarError:
        raise
    except Exception as exc:
        logger.warning("Failed to update Google Calendar event: %s", exc)
        raise CalendarError(f"failed to update calendar event: {exc}") from exc
