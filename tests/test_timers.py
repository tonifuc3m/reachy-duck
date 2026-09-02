"""Focused tests for in-memory local timers."""

from __future__ import annotations
import sys
import asyncio
from types import ModuleType
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock

import pytest

from reachy_duck.timers import TimerManager


def _clock() -> datetime:
    return datetime(2026, 9, 2, 17, 0, tzinfo=ZoneInfo("Europe/Madrid"))


async def _immediate_sleep(_duration: float) -> None:
    await asyncio.sleep(0)


async def _flush_timer_tasks() -> None:
    await asyncio.sleep(0)
    await asyncio.sleep(0)


def _tool_routine_classes():
    """Import Pydantic tool dispatch types without loading the hardware SDK."""
    if "reachy_mini" not in sys.modules:
        reachy_mini = ModuleType("reachy_mini")
        reachy_mini.ReachyMini = type("ReachyMini", (), {})
        sys.modules["reachy_mini"] = reachy_mini
    from reachy_duck.tools.core_tools import ToolDependencies
    from reachy_duck.tools.background_tool_manager import ToolCallRoutine

    return ToolCallRoutine, ToolDependencies


def test_timer_dependency_does_not_break_pydantic_tool_dispatch() -> None:
    """The timer service must not leave ToolCallRoutine with an unresolved type."""
    ToolCallRoutine, ToolDependencies = _tool_routine_classes()
    deps = ToolDependencies(reachy_mini=None, movement_manager=None, timer_manager=TimerManager(clock=_clock))

    routine = ToolCallRoutine(tool_name="set_timer", args_json_str="{}", deps=deps)

    assert routine.deps is deps


@pytest.mark.asyncio
async def test_creating_timer_returns_immediately_and_keeps_optional_label() -> None:
    """Scheduling does not wait for a timer's duration."""
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()

    async def delayed_sleep(_duration: float) -> None:
        sleep_started.set()
        await release_sleep.wait()

    manager = TimerManager(clock=_clock, sleep=delayed_sleep)
    result = manager.set_timer(600, " pasta ")

    assert result == {
        "id": "timer_1",
        "label": "pasta",
        "duration_seconds": 600.0,
        "expires_at": "2026-09-02T17:10:00+02:00",
        "status": "active",
    }
    await sleep_started.wait()
    assert manager.list_timers()[0]["status"] == "active"
    release_sleep.set()
    await _flush_timer_tasks()


@pytest.mark.asyncio
async def test_list_multiple_timers_and_duplicate_labels() -> None:
    """Duplicate labels remain distinct timers rather than being merged."""
    manager = TimerManager(clock=_clock, sleep=_immediate_sleep)
    first = manager.set_timer(10, "pasta")
    second = manager.set_timer(20, "pasta")
    unlabeled = manager.set_timer(30)

    timers = manager.list_timers()

    assert [timer["id"] for timer in timers] == [first["id"], second["id"], unlabeled["id"]]
    assert [timer["label"] for timer in timers] == ["pasta", "pasta", None]
    assert [timer["remaining_seconds"] for timer in timers] == [10.0, 20.0, 30.0]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_cancelling_active_timer_prevents_expiration() -> None:
    """Cancellation changes only an active timer and stops its task."""
    sleep_started = asyncio.Event()

    async def delayed_sleep(_duration: float) -> None:
        sleep_started.set()
        await asyncio.Event().wait()

    manager = TimerManager(clock=_clock, sleep=delayed_sleep)
    created = manager.set_timer(10)
    await sleep_started.wait()

    assert manager.cancel_timer(str(created["id"])) == {"id": "timer_1", "label": None, "status": "cancelled"}
    assert manager.cancel_timer(str(created["id"])) == {"error": "timer 'timer_1' is already cancelled"}
    assert manager.cancel_timer("timer_missing") == {"error": "timer 'timer_missing' does not exist"}

    await manager.shutdown()


@pytest.mark.asyncio
async def test_expiry_is_pending_until_it_can_be_announced_and_consumed_once() -> None:
    """An unavailable conversation leaves one pending expiry for the next turn."""
    manager = TimerManager(clock=_clock, sleep=_immediate_sleep)
    created = manager.set_timer(1, "oven")
    await _flush_timer_tasks()

    assert manager.list_timers() == [
        {
            "id": created["id"],
            "label": "oven",
            "duration_seconds": 1.0,
            "expires_at": "2026-09-02T17:00:01+02:00",
            "status": "expired",
            "remaining_seconds": 0.0,
        }
    ]
    announce = AsyncMock()
    manager.set_announcer(announce)

    await manager.announce_pending()
    await manager.announce_pending()

    announce.assert_awaited_once_with("Your oven timer is done.")
    assert manager.list_timers() == []


@pytest.mark.asyncio
async def test_expiry_uses_live_announcer_when_supported() -> None:
    """A live handler receives the normal injected announcement without a user turn."""
    announce = AsyncMock()
    manager = TimerManager(clock=_clock, sleep=_immediate_sleep)
    manager.set_announcer(announce)

    manager.set_timer(1)
    await _flush_timer_tasks()

    announce.assert_awaited_once_with("Your timer is done.")
    assert manager.list_timers() == []


@pytest.mark.asyncio
async def test_shutdown_cancels_active_timer_tasks() -> None:
    """App shutdown cancels outstanding sleeps without waiting for expiry."""
    sleep_started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked_sleep(_duration: float) -> None:
        sleep_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    manager = TimerManager(clock=_clock, sleep=blocked_sleep)
    manager.set_timer(60)
    await sleep_started.wait()

    await manager.shutdown()

    assert cancelled.is_set()
    assert manager._tasks == {}
