"""Google Calendar persistence and API access, independent of Reachy hardware."""

from __future__ import annotations
import logging
from typing import Any, Protocol, cast
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from reachy_duck.memory import persistent_data_directory
from reachy_duck.time_context import (
    TimeContextError,
    current_timezone,
)


logger = logging.getLogger(__name__)

GOOGLE_DIRECTORY_NAME = "google"
CLIENT_SECRET_FILENAME = "client_secret.json"
TOKEN_FILENAME = "token.json"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
DEFAULT_EVENT_DURATION = timedelta(minutes=30)


class CalendarService(Protocol):
    """Subset of the discovery service used by this module."""

    def events(self) -> Any:
        """Return the Calendar events resource."""


class CalendarError(RuntimeError):
    """Expected local authentication or Calendar API failure."""


def google_directory_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the install-independent Google credential directory for an app instance."""
    root = Path(instance_path).expanduser() if instance_path is not None else persistent_data_directory().parent
    return root / GOOGLE_DIRECTORY_NAME


def client_secret_path_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the locally supplied OAuth client configuration path."""
    return google_directory_for_instance(instance_path) / CLIENT_SECRET_FILENAME


def token_path_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the refreshable OAuth token path."""
    return google_directory_for_instance(instance_path) / TOKEN_FILENAME


def resolve_timezone(timezone_name: str | None = None) -> ZoneInfo:
    """Compatibility wrapper around the shared temporal timezone resolver."""
    try:
        return current_timezone(timezone_name)
    except TimeContextError as exc:
        raise CalendarError(str(exc)) from exc


def parse_aware_datetime(value: str, *, timezone: ZoneInfo) -> datetime:
    """Parse an ISO-8601 datetime with an explicit UTC offset or timezone."""
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
    """Persist OAuth tokens outside application code with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    path.chmod(0o600)


def authorize_google_calendar(*, instance_path: str | Path | None = None, port: int = 8080) -> Path:
    """Run local-loopback installed-app OAuth and save the resulting token."""
    if not 1 <= port <= 65535:
        raise CalendarError("OAuth port must be between 1 and 65535")

    client_path = client_secret_path_for_instance(instance_path)
    if not client_path.is_file():
        raise CalendarError(f"OAuth client file not found: {client_path}")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise CalendarError("Google Calendar dependencies are not installed") from exc

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), [CALENDAR_SCOPE])
        credentials = flow.run_local_server(host="127.0.0.1", port=port, open_browser=False)
        token_path = token_path_for_instance(instance_path)
        _write_private_token(credentials, token_path)
    except OSError as exc:
        raise CalendarError(f"OAuth authorization failed: {exc}") from exc
    return token_path


def build_calendar_service(*, instance_path: str | Path | None = None) -> CalendarService:
    """Load or refresh persisted credentials and construct the official Calendar client."""
    token_path = token_path_for_instance(instance_path)
    if not token_path.is_file():
        raise CalendarError("Google Calendar is not connected; run reachy-duck google-auth first")

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise CalendarError("Google Calendar dependencies are not installed") from exc

    try:
        credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_path), [CALENDAR_SCOPE]
        )
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CalendarError("Google Calendar authorization expired; run reachy-duck google-auth again")
            credentials.refresh(Request())
            _write_private_token(credentials, token_path)
        return cast(CalendarService, build("calendar", "v3", credentials=credentials, cache_discovery=False))
    except CalendarError:
        raise
    except Exception as exc:
        logger.warning("Failed to initialize Google Calendar client: %s", exc)
        raise CalendarError(f"Google Calendar authentication failed: {exc}") from exc


def create_calendar_event(
    *,
    title: str,
    start: str,
    end: str | None = None,
    description: str | None = None,
    timezone_name: str | None = None,
    service: CalendarService | None = None,
    instance_path: str | Path | None = None,
) -> dict[str, str]:
    """Create one timed event on the user's primary calendar."""
    if not isinstance(title, str) or not title.strip():
        raise CalendarError("title must be a non-empty string")
    if end is not None and not isinstance(end, str):
        raise CalendarError("end datetime must be an ISO-8601 string with a UTC offset")
    if description is not None and not isinstance(description, str):
        raise CalendarError("description must be a string")
    timezone = resolve_timezone(timezone_name)
    start_at = parse_aware_datetime(start, timezone=timezone)
    end_at = parse_aware_datetime(end, timezone=timezone) if end else start_at + DEFAULT_EVENT_DURATION
    if end_at <= start_at:
        raise CalendarError("end datetime must be after start datetime")

    body: dict[str, Any] = {
        "summary": title.strip(),
        "start": {"dateTime": start_at.isoformat(), "timeZone": timezone.key},
        "end": {"dateTime": end_at.isoformat(), "timeZone": timezone.key},
    }
    if description and description.strip():
        body["description"] = description.strip()

    try:
        event = (
            (service or build_calendar_service(instance_path=instance_path))
            .events()
            .insert(calendarId="primary", body=body)
            .execute()
        )
    except CalendarError:
        raise
    except Exception as exc:
        logger.warning("Failed to create Google Calendar event: %s", exc)
        raise CalendarError(f"failed to create calendar event: {exc}") from exc
    return {
        "title": str(event.get("summary", title.strip())),
        "start": str(event.get("start", {}).get("dateTime", start_at.isoformat())),
        "end": str(event.get("end", {}).get("dateTime", end_at.isoformat())),
    }


def _format_event_time(event_time: dict[str, str], timezone: ZoneInfo) -> str:
    """Format an API event time compactly for a spoken response."""
    if "date" in event_time:
        return f"all day {event_time['date']}"
    value = event_time.get("dateTime")
    if not value:
        return "unscheduled"
    return parse_aware_datetime(value, timezone=timezone).strftime("%a %d %b, %H:%M")


def list_calendar_events(
    *,
    start: str,
    end: str,
    timezone_name: str | None = None,
    service: CalendarService | None = None,
    instance_path: str | Path | None = None,
) -> list[dict[str, str]]:
    """Return primary-calendar events in an interval in a concise display shape."""
    timezone = resolve_timezone(timezone_name)
    start_at = parse_aware_datetime(start, timezone=timezone)
    end_at = parse_aware_datetime(end, timezone=timezone)
    if end_at <= start_at:
        raise CalendarError("end datetime must be after start datetime")
    try:
        response = (
            (service or build_calendar_service(instance_path=instance_path))
            .events()
            .list(
                calendarId="primary",
                timeMin=start_at.isoformat(),
                timeMax=end_at.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except CalendarError:
        raise
    except Exception as exc:
        logger.warning("Failed to list Google Calendar events: %s", exc)
        raise CalendarError(f"failed to list calendar events: {exc}") from exc

    return [
        {
            "title": str(event.get("summary", "Untitled event")),
            "start": _format_event_time(event.get("start", {}), timezone),
            "end": _format_event_time(event.get("end", {}), timezone),
        }
        for event in response.get("items", [])
        if event.get("status") != "cancelled"
    ]
