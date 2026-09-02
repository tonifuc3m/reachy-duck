"""In-memory relative timers for the current Reachy Duck process."""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections.abc import Callable, Awaitable

from reachy_duck.time_context import now


logger = logging.getLogger(__name__)

TimerAnnouncer = Callable[[str], Awaitable[None]]


@dataclass
class Timer:
    """One relative timer kept only for the lifetime of this process."""

    id: str
    label: str | None
    created_at: datetime
    duration_seconds: float
    expires_at: datetime
    status: str = "active"

    def payload(
        self,
        *,
        include_remaining: bool = False,
        current_time: datetime | None = None,
    ) -> dict[str, object]:
        """Return the concise public representation of this timer."""
        payload: dict[str, object] = {
            "id": self.id,
            "label": self.label,
            "duration_seconds": self.duration_seconds,
            "expires_at": self.expires_at.isoformat(timespec="seconds"),
            "status": self.status,
        }
        if include_remaining:
            remaining = (
                max(0.0, (self.expires_at - (current_time or now())).total_seconds())
                if self.status == "active"
                else 0.0
            )
            payload["remaining_seconds"] = remaining
        return payload


class TimerManager:
    """Schedule small in-memory timers using the application's asyncio loop."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Initialize empty process-local timer state with injectable test time."""
        self._clock = clock
        self._sleep = sleep
        self._timers: dict[str, Timer] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._pending_expired_timers: list[Timer] = []
        self._announcer: TimerAnnouncer | None = None
        self._next_id = 1

    def set_announcer(self, announcer: TimerAnnouncer | None) -> None:
        """Set the current realtime-message injection callback, if available."""
        self._announcer = announcer

    def set_timer(self, duration_seconds: float, label: str | None = None) -> dict[str, object]:
        """Create a relative timer and schedule its expiry without waiting for it."""
        if not isinstance(duration_seconds, (int, float)) or isinstance(duration_seconds, bool):
            raise ValueError("duration_seconds must be a positive number")
        duration = float(duration_seconds)
        if duration <= 0 or duration == float("inf") or duration != duration:
            raise ValueError("duration_seconds must be a finite positive number")
        if label is not None and not isinstance(label, str):
            raise ValueError("label must be a string or null")
        normalized_label = label.strip() if isinstance(label, str) else None
        if normalized_label == "":
            normalized_label = None

        created_at = self._clock()
        timer = Timer(
            id=f"timer_{self._next_id}",
            label=normalized_label,
            created_at=created_at,
            duration_seconds=duration,
            expires_at=created_at + timedelta(seconds=duration),
        )
        self._next_id += 1
        self._timers[timer.id] = timer
        self._tasks[timer.id] = asyncio.create_task(self._expire_after_delay(timer), name=timer.id)
        return timer.payload()

    def list_timers(self) -> list[dict[str, object]]:
        """Return active timers and any expired timer that still needs announcing."""
        timers = [timer for timer in self._timers.values() if timer.status == "active"]
        timers.extend(timer for timer in self._pending_expired_timers if timer not in timers)
        current_time = self._clock()
        return [timer.payload(include_remaining=True, current_time=current_time) for timer in timers]

    def cancel_timer(self, timer_id: str) -> dict[str, object]:
        """Cancel one active timer, returning a clear result for other states."""
        timer = self._timers.get(timer_id)
        if timer is None:
            return {"error": f"timer {timer_id!r} does not exist"}
        if timer.status != "active":
            return {"error": f"timer {timer_id!r} is already {timer.status}"}
        timer.status = "cancelled"
        task = self._tasks.pop(timer_id, None)
        if task is not None:
            task.cancel()
        return {"id": timer.id, "label": timer.label, "status": timer.status}

    async def announce_pending(self) -> None:
        """Try each unannounced expiry once on a normal subsequent user turn."""
        for timer in list(self._pending_expired_timers):
            if await self._announce(timer):
                self._pending_expired_timers.remove(timer)

    async def shutdown(self) -> None:
        """Cancel outstanding timer tasks when the app process is stopping."""
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _expire_after_delay(self, timer: Timer) -> None:
        try:
            await self._sleep(timer.duration_seconds)
            if timer.status != "active":
                return
            timer.status = "expired"
            if not await self._announce(timer):
                self._pending_expired_timers.append(timer)
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._tasks.get(timer.id) is current:
                self._tasks.pop(timer.id, None)

    async def _announce(self, timer: Timer) -> bool:
        if self._announcer is None:
            return False
        label = f" {timer.label}" if timer.label else ""
        try:
            await self._announcer(f"Your{label} timer is done.")
        except Exception as exc:
            logger.info("Could not announce expired timer %s yet: %s", timer.id, exc)
            return False
        return True
