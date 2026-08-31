"""Timezone-aware temporal context from the local system clock."""

from __future__ import annotations
import os
import logging
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from collections.abc import Callable


logger = logging.getLogger(__name__)

TIMEZONE_ENV = "REACHY_DUCK_TIMEZONE"
DEFAULT_TIMEZONE = "Europe/Madrid"


class TimeContextError(ValueError):
    """Raised when an explicitly requested IANA timezone is invalid."""


def _zoneinfo_or_none(name: str | None) -> ZoneInfo | None:
    """Resolve a non-empty IANA timezone name without raising."""
    candidate = (name or "").strip()
    if not candidate:
        return None
    try:
        return ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return None


def _system_timezone() -> ZoneInfo | None:
    """Best-effort discovery of the host's IANA timezone without network access."""
    for name in (os.getenv("TZ"), _read_etc_timezone(), _read_localtime_symlink()):
        timezone = _zoneinfo_or_none(name)
        if timezone is not None:
            return timezone

    local_timezone = datetime.now().astimezone().tzinfo
    if isinstance(local_timezone, ZoneInfo):
        return local_timezone
    return None


def _read_etc_timezone() -> str | None:
    """Read the conventional Linux timezone name when it is available."""
    try:
        return Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_localtime_symlink() -> str | None:
    """Derive an IANA name from a conventional /etc/localtime symlink."""
    try:
        target = Path("/etc/localtime").resolve(strict=True)
        return str(target.relative_to("/usr/share/zoneinfo"))
    except (OSError, ValueError):
        return None


def current_timezone(timezone_name: str | None = None) -> ZoneInfo:
    """Return the active timezone: explicit config, host timezone, then Madrid.

    An explicit function argument is strict so callers that request a particular
    timezone receive a clear error instead of silently storing data elsewhere.
    Invalid environment configuration is logged and falls through to the host
    timezone and finally the documented default.
    """
    if timezone_name is not None:
        if not isinstance(timezone_name, str):
            raise TimeContextError("timezone must be an IANA timezone name")
        timezone = _zoneinfo_or_none(timezone_name)
        if timezone is None:
            raise TimeContextError(f"unknown timezone: {timezone_name}")
        return timezone

    configured_name = os.getenv(TIMEZONE_ENV)
    if configured_name and configured_name.strip():
        timezone = _zoneinfo_or_none(configured_name)
        if timezone is not None:
            return timezone
        logger.warning("Ignoring invalid %s=%r", TIMEZONE_ENV, configured_name)

    return _system_timezone() or ZoneInfo(DEFAULT_TIMEZONE)


def now(
    *,
    timezone_name: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> datetime:
    """Return the current system time as a timezone-aware datetime."""
    timezone = current_timezone(timezone_name)
    if clock is None:
        return datetime.now(timezone)

    instant = clock()
    if instant.tzinfo is None or instant.utcoffset() is None:
        return instant.replace(tzinfo=timezone)
    return instant.astimezone(timezone)


def today(*, timezone_name: str | None = None, clock: Callable[[], datetime] | None = None) -> date:
    """Return the current local date in the active timezone."""
    return now(timezone_name=timezone_name, clock=clock).date()


def current_datetime_payload(*, clock: Callable[[], datetime] | None = None) -> dict[str, str]:
    """Return concise, precise temporal context for LLM tools."""
    local_now = now(clock=clock)
    offset = local_now.strftime("%z")
    return {
        "datetime": local_now.isoformat(timespec="seconds"),
        "date": local_now.date().isoformat(),
        "time": local_now.strftime("%H:%M:%S"),
        "weekday": local_now.strftime("%A"),
        "timezone": getattr(local_now.tzinfo, "key", str(local_now.tzinfo)),
        "utc_offset": f"{offset[:3]}:{offset[3:]}",
    }


def format_session_temporal_context(*, clock: Callable[[], datetime] | None = None) -> str:
    """Format the session-start temporal grounding for system instructions."""
    local_now = now(clock=clock)
    timezone_name = getattr(local_now.tzinfo, "key", str(local_now.tzinfo))
    return (
        "Current local date and time at the start of this conversation:\n"
        f"{local_now.strftime('%A, %d %B %Y, %H:%M')}\n"
        f"Timezone: {timezone_name} ({local_now.strftime('%z')[:3]}:{local_now.strftime('%z')[3:]})\n\n"
        "Treat this as session-start context, not a live clock. Never guess the current date or time. "
        "Use get_current_datetime before answering or acting on time-sensitive requests, especially relative "
        "calendar or reminder requests."
    )
