"""Read-only snapshots of the local Reachy Mini daemon state."""

from __future__ import annotations
import asyncio
import logging
from typing import Any
from dataclasses import field, asdict, dataclass

import httpx

from reachy_duck.config import config


logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 0.75
MAX_RESPONSE_BYTES = 64 * 1024
_AWAKE_MOTOR_CONTROL_MODES = {"enabled", "gravity_compensation"}


@dataclass
class RobotStatus:
    """Small, stable representation of read-only daemon state."""

    daemon_reachable: bool
    daemon_state: str | None = None
    robot_ready: bool | None = None
    daemon_error: str | None = None
    backend_error: str | None = None
    motor_control_mode: str | None = None
    awake: bool | None = None
    app_lock_state: str | None = None
    active_app: str | None = None
    speaker_volume: float | int | None = None
    microphone_volume: float | int | None = None
    speech_detected: bool | None = None
    wlan_ip: str | None = None
    reachy_version: str | None = None
    hardware_id: str | None = None
    wireless_version: bool | None = None
    battery_available: bool = False
    battery_percent: float | None = None
    charging: bool | None = None
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return only normalized, model-visible fields."""
        return asdict(self)


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _volume(payload: object) -> float | int | None:
    if isinstance(payload, dict):
        return _number(payload.get("volume"))
    return _number(payload)


class ReachyDaemonStatusClient:
    """Fetch independent status endpoints from the local Reachy Mini daemon."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Use the configured daemon endpoint or an injected client for tests."""
        self._base_url = (base_url or config.REACHY_DAEMON_API_BASE_URL).rstrip("/")
        self._client = client

    async def _get_json(self, client: httpx.AsyncClient, path: str) -> object:
        response = await client.get(f"{self._base_url}{path}")
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ValueError("response exceeds the status size limit")
        return response.json()

    async def snapshot(self) -> RobotStatus:
        """Read a fresh daemon snapshot, preserving useful partial results."""
        if self._client is not None:
            return await self._snapshot_with_client(self._client)
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            return await self._snapshot_with_client(client)

    async def _snapshot_with_client(self, client: httpx.AsyncClient) -> RobotStatus:
        try:
            daemon_payload = await self._get_json(client, "/daemon/status")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Reachy Mini daemon status is unavailable: %s", exc)
            return RobotStatus(
                daemon_reachable=False,
                problems=["Reachy Mini daemon is not reachable."],
            )

        if not isinstance(daemon_payload, dict):
            logger.warning("Reachy Mini daemon status returned a non-object response")
            return RobotStatus(
                daemon_reachable=False,
                problems=["Reachy Mini daemon status is unavailable."],
            )

        backend = daemon_payload.get("backend_status")
        backend_status = backend if isinstance(backend, dict) else {}
        motor_control_mode = _string(backend_status.get("motor_control_mode"))
        status = RobotStatus(
            daemon_reachable=True,
            daemon_state=_string(daemon_payload.get("state")),
            robot_ready=_boolean(backend_status.get("ready")),
            daemon_error=_string(daemon_payload.get("error")),
            backend_error=_string(backend_status.get("error")),
            motor_control_mode=motor_control_mode,
            awake=(motor_control_mode in _AWAKE_MOTOR_CONTROL_MODES) if motor_control_mode is not None else None,
            wlan_ip=_string(daemon_payload.get("wlan_ip")),
            reachy_version=_string(daemon_payload.get("version")),
            hardware_id=_string(daemon_payload.get("hardware_id")),
            wireless_version=_boolean(daemon_payload.get("wireless_version")),
        )
        if status.daemon_error:
            status.problems.append("The Reachy Mini daemon reported an error.")
        if status.backend_error:
            status.problems.append("The Reachy Mini backend reported an error.")
        if status.robot_ready is False:
            status.problems.append("The Reachy Mini backend is not ready.")

        results = await asyncio.gather(
            self._get_optional(client, "/daemon/robot-app-lock-status", "Managed app status is unavailable."),
            self._get_optional(client, "/volume/current", "Speaker volume status is unavailable."),
            self._get_optional(client, "/volume/microphone/current", "Microphone volume status is unavailable."),
            self._get_optional(client, "/state/doa", "Speech detection status is unavailable."),
        )
        (
            (lock_payload, lock_problem),
            (speaker_payload, speaker_problem),
            (microphone_payload, microphone_problem),
            (
                doa_payload,
                doa_problem,
            ),
        ) = results
        for problem in (lock_problem, speaker_problem, microphone_problem, doa_problem):
            if problem:
                status.problems.append(problem)

        if isinstance(lock_payload, dict):
            status.app_lock_state = _string(lock_payload.get("state"))
            status.active_app = _string(lock_payload.get("holder_name"))
        status.speaker_volume = _volume(speaker_payload)
        status.microphone_volume = _volume(microphone_payload)
        if isinstance(doa_payload, dict):
            status.speech_detected = _boolean(doa_payload.get("speech_detected"))
        return status

    async def _get_optional(
        self, client: httpx.AsyncClient, path: str, problem: str
    ) -> tuple[object | None, str | None]:
        try:
            return await self._get_json(client, path), None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Reachy Mini status endpoint %s is unavailable: %s", path, exc)
            return None, problem


async def get_robot_status() -> dict[str, Any]:
    """Return a fresh normalized snapshot from the configured local daemon."""
    return (await ReachyDaemonStatusClient().snapshot()).to_dict()
