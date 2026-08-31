"""Focused tests for the timezone-aware temporal service and tool."""

import sys
from types import ModuleType
from datetime import datetime

import pytest

import reachy_duck.prompts as prompts_mod
import reachy_duck.time_context as time_context
from reachy_duck.config import LOCKED_PROFILE, config


def _clock(value: datetime):
    return lambda: value


def _tool_classes():
    """Import tool modules without initializing the hardware SDK in unit tests."""
    if "reachy_mini" not in sys.modules:
        reachy_mini = ModuleType("reachy_mini")
        reachy_mini.ReachyMini = type("ReachyMini", (), {})
        sys.modules["reachy_mini"] = reachy_mini
    from reachy_duck.tools.core_tools import ToolDependencies, initialize_tools
    from reachy_duck.tools.get_current_datetime import GetCurrentDatetime

    return GetCurrentDatetime, ToolDependencies, initialize_tools


def test_configured_timezone_and_payload_are_timezone_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured timezone controls current date, weekday, and offset."""
    monkeypatch.setenv(time_context.TIMEZONE_ENV, "Europe/Madrid")
    payload = time_context.current_datetime_payload(
        clock=_clock(datetime(2026, 8, 31, 15, 0, tzinfo=time_context.ZoneInfo("UTC")))
    )

    assert time_context.current_timezone().key == "Europe/Madrid"
    assert payload == {
        "datetime": "2026-08-31T17:00:00+02:00",
        "date": "2026-08-31",
        "time": "17:00:00",
        "weekday": "Monday",
        "timezone": "Europe/Madrid",
        "utc_offset": "+02:00",
    }
    assert (
        time_context.today(clock=_clock(datetime(2026, 8, 31, 15, 0, tzinfo=time_context.ZoneInfo("UTC")))).isoformat()
        == "2026-08-31"
    )


def test_invalid_or_missing_config_falls_back_to_system_then_madrid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad environment values cannot make temporal operations unusable."""
    monkeypatch.setenv(time_context.TIMEZONE_ENV, "not/a-timezone")
    monkeypatch.setattr(time_context, "_system_timezone", lambda: time_context.ZoneInfo("UTC"))
    assert time_context.current_timezone().key == "UTC"

    monkeypatch.delenv(time_context.TIMEZONE_ENV)
    monkeypatch.setattr(time_context, "_system_timezone", lambda: None)
    assert time_context.current_timezone().key == "Europe/Madrid"

    with pytest.raises(time_context.TimeContextError, match="unknown timezone"):
        time_context.current_timezone("not/a-timezone")


@pytest.mark.parametrize(
    ("instant", "offset"),
    [
        (datetime(2026, 1, 15, 12, 0, tzinfo=time_context.ZoneInfo("UTC")), "+01:00"),
        (datetime(2026, 7, 15, 12, 0, tzinfo=time_context.ZoneInfo("UTC")), "+02:00"),
    ],
)
def test_madrid_dst_offset_uses_iana_rules(instant: datetime, offset: str) -> None:
    """CET and CEST offsets come from ZoneInfo rather than custom DST logic."""
    assert time_context.now(timezone_name="Europe/Madrid", clock=_clock(instant)).strftime("%z") == offset.replace(
        ":", ""
    )


def test_locked_session_instructions_include_frozen_temporal_context(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each locked-profile session gets temporal grounding when instructions are built."""
    monkeypatch.setattr(config, "REACHY_MINI_CUSTOM_PROFILE", LOCKED_PROFILE)
    monkeypatch.setattr(
        prompts_mod,
        "format_session_temporal_context",
        lambda: "Current local date and time at the start of this conversation:\\nMonday, 31 August 2026, 15:00",
    )

    instructions = prompts_mod.get_session_instructions(instance_path=tmp_path)

    assert "Monday, 31 August 2026, 15:00" in instructions
    assert instructions.index("Current local date") < instructions.index("You are Reachy")


@pytest.mark.asyncio
async def test_current_datetime_tool_schema_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registered LLM tool returns concise fresh temporal fields."""
    GetCurrentDatetime, ToolDependencies, _ = _tool_classes()
    monkeypatch.setattr(
        "reachy_duck.tools.get_current_datetime.current_datetime_payload",
        lambda: {"datetime": "2026-08-31T15:00:00+02:00", "timezone": "Europe/Madrid"},
    )
    tool = GetCurrentDatetime()
    result = await tool(ToolDependencies(reachy_mini=None, movement_manager=None))

    assert tool.spec()["name"] == "get_current_datetime"
    assert tool.spec()["parameters"] == {"type": "object", "properties": {}, "additionalProperties": False}
    assert result == {"datetime": "2026-08-31T15:00:00+02:00", "timezone": "Europe/Madrid"}


def test_current_datetime_tool_is_registered_for_locked_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """The locked profile advertises the time tool through the standard registry."""
    _, _, initialize_tools = _tool_classes()
    monkeypatch.setattr(config, "REACHY_MINI_CUSTOM_PROFILE", LOCKED_PROFILE)
    initialize_tools(force=True)
    from reachy_duck.tools.core_tools import ALL_TOOLS

    assert "get_current_datetime" in ALL_TOOLS
