from pathlib import Path

import pytest

import reachy_duck.google_calendar as google_calendar_mod
from reachy_duck.google_calendar import (
    CalendarError,
    list_calendar_events,
    parse_aware_datetime,
    create_calendar_event,
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

    def insert(self, **kwargs: object) -> FakeRequest:
        """Record an event insertion and return its fake response."""
        self.insert_args = kwargs
        body = kwargs["body"]
        assert isinstance(body, dict)
        return FakeRequest({"summary": body["summary"], "start": body["start"], "end": body["end"]})

    def list(self, **kwargs: object) -> FakeRequest:
        """Record an event-list request and return fake events."""
        self.list_args = kwargs
        return FakeRequest(
            {
                "items": [
                    {
                        "summary": "Dentist",
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
    assert result == [
        {"title": "Dentist", "start": "Fri 04 Sep, 18:00", "end": "Fri 04 Sep, 18:30"},
        {"title": "Holiday", "start": "all day 2026-09-05", "end": "all day 2026-09-06"},
    ]


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
