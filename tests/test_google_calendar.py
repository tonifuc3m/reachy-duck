# ruff: noqa: D101, D102, D103

from pathlib import Path

import pytest

import reachy_duck.google_calendar as google_calendar_mod
from reachy_duck.google_calendar import (
    CalendarError,
    list_calendars,
    recurrence_rule,
    resolve_calendar_id,
    list_calendar_events,
    parse_aware_datetime,
    create_calendar_event,
    update_calendar_event,
    token_path_for_instance,
    google_directory_for_instance,
)


class FakeRequest:
    """Fake discovery request returning a prepared response."""

    def __init__(self, response: dict) -> None:
        """Store the result returned by execute."""
        self.response = response

    def execute(self) -> dict:
        """Return the prepared fake API response."""
        return self.response


class FakeEvents:
    """Fake events resource recording Calendar API calls."""

    def __init__(self) -> None:
        """Initialize recorded request arguments."""
        self.insert_args: dict | None = None
        self.list_args: dict | None = None
        self.update_args: dict | None = None
        self.move_args: dict | None = None
        self.event = {
            "id": "dentist-id",
            "summary": "Dentist",
            "description": "Old",
            "start": {"dateTime": "2026-09-04T18:00:00+02:00"},
            "end": {"dateTime": "2026-09-04T18:30:00+02:00"},
        }

    def insert(self, **kwargs: object) -> FakeRequest:
        """Record an event insertion and return its fake response."""
        self.insert_args = kwargs
        body = kwargs["body"]
        assert isinstance(body, dict)
        return FakeRequest(
            {"id": "created-id", "summary": body["summary"], "start": body["start"], "end": body["end"]}
        )

    def get(self, **kwargs: object) -> FakeRequest:
        if kwargs["eventId"] == "series-id":
            master = dict(self.event)
            master["id"] = "series-id"
            master.pop("recurringEventId", None)
            return FakeRequest(master)
        return FakeRequest(dict(self.event))

    def update(self, **kwargs: object) -> FakeRequest:
        self.update_args = kwargs
        body = kwargs["body"]
        assert isinstance(body, dict)
        return FakeRequest(body)

    def move(self, **kwargs: object) -> FakeRequest:
        self.move_args = kwargs
        return FakeRequest(dict(self.event))

    def list(self, **kwargs: object) -> FakeRequest:
        """Record an event-list request and return fake events."""
        self.list_args = kwargs
        return FakeRequest(
            {
                "items": [
                    {
                        "summary": "Dentist",
                        "id": "dentist-id",
                        "start": {"dateTime": "2026-09-04T18:00:00+02:00"},
                        "end": {"dateTime": "2026-09-04T18:30:00+02:00"},
                    },
                    {"summary": "Holiday", "start": {"date": "2026-09-05"}, "end": {"date": "2026-09-06"}},
                    {"summary": "Cancelled", "status": "cancelled", "start": {}, "end": {}},
                ]
            }
        )


class FakeService:
    """Fake Calendar discovery service."""

    def __init__(self) -> None:
        """Create its events resource."""
        self.events_api = FakeEvents()

    def events(self) -> FakeEvents:
        """Return the fake events resource."""
        return self.events_api

    def calendarList(self) -> "FakeCalendars":
        return FakeCalendars()


class FakeCalendars:
    def list(self, **kwargs: object) -> FakeRequest:
        return FakeRequest(
            {
                "items": [
                    {"id": "primary", "summary": "Primary", "primary": True, "accessRole": "owner"},
                    {"id": "work@example.com", "summary": "Work", "accessRole": "writer"},
                ]
            }
        )


def test_google_paths_are_outside_replaceable_data_files(tmp_path: Path) -> None:
    """Credentials should share the persistent instance root, not package code."""
    assert google_directory_for_instance(tmp_path) == tmp_path / "google"
    assert token_path_for_instance(tmp_path) == tmp_path / "google" / "token.json"


def test_default_google_path_uses_persistent_user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default credentials should never be placed in a source checkout."""
    monkeypatch.setattr(google_calendar_mod, "persistent_data_directory", lambda: tmp_path / "reachy_duck" / "data")

    assert google_directory_for_instance() == tmp_path / "reachy_duck" / "google"


def test_create_event_defaults_to_thirty_minutes_and_preserves_timezone() -> None:
    """Creating an event should use an explicit timezone and default duration."""
    service = FakeService()

    result = create_calendar_event(
        title="Buy milk",
        start="2026-09-01T19:00:00+02:00",
        timezone_name="Europe/Madrid",
        service=service,
    )

    body = service.events_api.insert_args["body"]  # type: ignore[index]
    assert body["start"] == {"dateTime": "2026-09-01T19:00:00+02:00", "timeZone": "Europe/Madrid"}
    assert body["end"] == {"dateTime": "2026-09-01T19:30:00+02:00", "timeZone": "Europe/Madrid"}
    assert result["title"] == "Buy milk"


def test_list_events_requests_interval_and_returns_concise_events() -> None:
    """Listing should constrain the interval and produce speech-friendly values."""
    service = FakeService()

    result = list_calendar_events(
        start="2026-09-04T00:00:00+02:00",
        end="2026-09-06T00:00:00+02:00",
        timezone_name="Europe/Madrid",
        service=service,
    )

    assert service.events_api.list_args["calendarId"] == "primary"  # type: ignore[index]
    assert service.events_api.list_args["singleEvents"] is True  # type: ignore[index]
    assert result[0]["id"] == "dentist-id"
    assert result[0]["title"] == "Dentist"
    assert result[1]["start"] == "all day 2026-09-05"


def test_calendar_rejects_naive_or_invalid_intervals() -> None:
    """Calendar operations must refuse datetimes without offsets and bad intervals."""
    with pytest.raises(CalendarError, match="UTC offset"):
        parse_aware_datetime("2026-09-01T19:00:00", timezone=__import__("zoneinfo").ZoneInfo("Europe/Madrid"))
    with pytest.raises(CalendarError, match="after start"):
        list_calendar_events(
            start="2026-09-02T19:00:00+02:00",
            end="2026-09-01T19:00:00+02:00",
            service=FakeService(),
        )


def test_recurrence_rules_support_weekdays_until_and_count() -> None:
    timezone = __import__("zoneinfo").ZoneInfo("Europe/Madrid")
    assert (
        recurrence_rule(frequency="weekly", weekdays=["monday", "friday"], timezone=timezone)
        == "RRULE:FREQ=WEEKLY;BYDAY=MO,FR"
    )
    assert (
        recurrence_rule(frequency="monthly", until="2026-12-01T00:00:00+01:00", timezone=timezone)
        == "RRULE:FREQ=MONTHLY;UNTIL=20261130T230000Z"
    )
    assert recurrence_rule(frequency="daily", count=3, timezone=timezone) == "RRULE:FREQ=DAILY;COUNT=3"


def test_create_rich_event_invites_and_sends_updates() -> None:
    service = FakeService()
    create_calendar_event(
        title="Planning",
        start="2026-09-01T09:00:00+02:00",
        description="Q4",
        attendees=["alice@example.com"],
        color="blue",
        recurrence={"frequency": "weekly", "weekdays": ["monday"]},
        reminders=[{"method": "popup", "minutes": 10}],
        create_google_meet=True,
        calendar="Work",
        timezone_name="Europe/Madrid",
        service=service,
    )
    args = service.events_api.insert_args
    assert args["calendarId"] == "work@example.com"
    assert args["sendUpdates"] == "all"
    assert args["conferenceDataVersion"] == 1
    assert args["body"]["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    assert args["body"]["attendees"] == [{"email": "alice@example.com"}]
    assert args["body"]["colorId"] == "9"


def test_calendar_resolution_and_duplicate_or_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeService()
    assert resolve_calendar_id("Work", service=service) == "work@example.com"
    assert resolve_calendar_id("work@example.com", service=service) == "work@example.com"
    assert list_calendars(service=service)[0]["primary"] is True
    with pytest.raises(CalendarError, match="not found"):
        resolve_calendar_id("Personal", service=service)
    monkeypatch.setattr(
        google_calendar_mod,
        "list_calendars",
        lambda **kwargs: [{"id": "a", "name": "Work"}, {"id": "b", "name": "Work"}],
    )
    with pytest.raises(CalendarError, match="multiple"):
        resolve_calendar_id("Work", service=service)


def test_invalid_color_and_ambiguous_event_are_rejected() -> None:
    with pytest.raises(CalendarError, match="unsupported color"):
        create_calendar_event(title="Test", start="2026-09-01T09:00:00+02:00", color="magenta", service=FakeService())
    service = FakeService()
    original_list = service.events_api.list
    service.events_api.list = lambda **kwargs: FakeRequest(
        {"items": [service.events_api.event, service.events_api.event]}
    )  # type: ignore[method-assign]
    with pytest.raises(CalendarError, match="multiple"):
        update_calendar_event(
            match_title="Dentist",
            match_start="2026-09-04T00:00:00+02:00",
            match_end="2026-09-05T00:00:00+02:00",
            description="New",
            service=service,
        )
    service.events_api.list = original_list  # type: ignore[method-assign]


def test_update_preserves_fields_adds_attendee_and_sends_invitation() -> None:
    service = FakeService()
    update_calendar_event(
        event_id="dentist-id",
        description="New",
        attendees=["bob@example.com"],
        attendee_action="add",
        color="tomato",
        create_google_meet=True,
        service=service,
    )
    args = service.events_api.update_args
    assert args["sendUpdates"] == "all"
    assert args["conferenceDataVersion"] == 1
    assert args["body"]["description"] == "New"
    assert args["body"]["attendees"] == [{"email": "bob@example.com"}]
    assert args["body"]["colorId"] == "11"


def test_recurring_instance_requires_scope_and_future_is_rejected() -> None:
    service = FakeService()
    service.events_api.event["recurringEventId"] = "series-id"
    with pytest.raises(CalendarError, match="occurrence"):
        update_calendar_event(event_id="dentist-id", description="New", service=service)
    with pytest.raises(CalendarError, match="future"):
        update_calendar_event(event_id="dentist-id", description="New", recurrence_scope="future", service=service)
    update_calendar_event(
        event_id="dentist-id",
        description="Series change",
        recurrence_scope="all",
        service=service,
    )
    assert service.events_api.update_args["eventId"] == "series-id"
