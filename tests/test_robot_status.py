from __future__ import annotations

import httpx
import pytest

from reachy_duck.robot_status import ReachyDaemonStatusClient


def status_payload(*, motor_control_mode: str | None = "enabled") -> dict[str, object]:
    """Return the documented daemon fields for a healthy Wireless robot."""
    backend: dict[str, object] = {"ready": True}
    if motor_control_mode is not None:
        backend["motor_control_mode"] = motor_control_mode
    return {
        "state": "running",
        "wireless_version": True,
        "backend_status": backend,
        "error": None,
        "wlan_ip": "192.168.1.23",
        "version": "1.10.0",
        "hardware_id": "reachy-mini-wireless",
    }


def status_client(responses: dict[str, httpx.Response | Exception]) -> ReachyDaemonStatusClient:
    """Build a daemon client with endpoint-specific mock responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        result = responses[request.url.path]
        if isinstance(result, Exception):
            raise result
        return result

    return ReachyDaemonStatusClient(
        "http://daemon.test/api",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_snapshot_reports_healthy_wireless_robot() -> None:
    """A complete daemon response becomes a concise normalized snapshot."""
    client = status_client(
        {
            "/api/daemon/status": httpx.Response(200, json=status_payload()),
            "/api/daemon/robot-app-lock-status": httpx.Response(
                200, json={"state": "local_app", "holder_name": "reachy_duck"}
            ),
            "/api/volume/current": httpx.Response(200, json=75),
            "/api/volume/microphone/current": httpx.Response(200, json={"volume": 40}),
            "/api/state/doa": httpx.Response(200, json={"speech_detected": False, "angle": 10}),
        }
    )

    snapshot = (await client.snapshot()).to_dict()

    assert snapshot == {
        "daemon_reachable": True,
        "daemon_state": "running",
        "robot_ready": True,
        "daemon_error": None,
        "backend_error": None,
        "motor_control_mode": "enabled",
        "awake": True,
        "app_lock_state": "local_app",
        "active_app": "reachy_duck",
        "speaker_volume": 75,
        "microphone_volume": 40,
        "speech_detected": False,
        "wlan_ip": "192.168.1.23",
        "reachy_version": "1.10.0",
        "hardware_id": "reachy-mini-wireless",
        "wireless_version": True,
        "battery_available": False,
        "battery_percent": None,
        "charging": None,
        "problems": [],
    }


@pytest.mark.asyncio
async def test_snapshot_preserves_daemon_and_backend_errors() -> None:
    """Daemon and backend errors remain distinct from backend readiness."""
    payload = status_payload()
    payload["error"] = "daemon fault"
    payload["backend_status"] = {"ready": False, "error": "backend fault", "motor_control_mode": "disabled"}
    client = status_client(
        {
            "/api/daemon/status": httpx.Response(200, json=payload),
            "/api/daemon/robot-app-lock-status": httpx.Response(200, json={"state": "free", "holder_name": None}),
            "/api/volume/current": httpx.Response(200, json=50),
            "/api/volume/microphone/current": httpx.Response(200, json=50),
            "/api/state/doa": httpx.Response(200, json={"speech_detected": False}),
        }
    )

    snapshot = await client.snapshot()

    assert snapshot.robot_ready is False
    assert snapshot.awake is False
    assert snapshot.daemon_error == "daemon fault"
    assert snapshot.backend_error == "backend fault"
    assert snapshot.problems == [
        "The Reachy Mini daemon reported an error.",
        "The Reachy Mini backend reported an error.",
        "The Reachy Mini backend is not ready.",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("motor_control_mode", "awake"),
    [("enabled", True), ("gravity_compensation", True), ("disabled", False), (None, None)],
)
async def test_snapshot_normalizes_documented_motor_modes(motor_control_mode: str | None, awake: bool | None) -> None:
    """Only enabled and gravity-compensation modes are considered awake."""
    client = status_client(
        {
            "/api/daemon/status": httpx.Response(200, json=status_payload(motor_control_mode=motor_control_mode)),
            "/api/daemon/robot-app-lock-status": httpx.Response(200, json={"state": "free"}),
            "/api/volume/current": httpx.Response(200, json=50),
            "/api/volume/microphone/current": httpx.Response(200, json=50),
            "/api/state/doa": httpx.Response(200, json={}),
        }
    )

    snapshot = await client.snapshot()

    assert snapshot.motor_control_mode == motor_control_mode
    assert snapshot.awake is awake
    assert snapshot.app_lock_state == "free"
    assert snapshot.active_app is None


@pytest.mark.asyncio
async def test_snapshot_returns_partial_results_when_secondary_endpoint_fails() -> None:
    """Independent secondary failures do not discard a usable daemon response."""
    request = httpx.Request("GET", "http://daemon.test/api/volume/microphone/current")
    client = status_client(
        {
            "/api/daemon/status": httpx.Response(200, json=status_payload()),
            "/api/daemon/robot-app-lock-status": httpx.Response(
                200, json={"state": "local_app", "holder_name": "reachy_duck"}
            ),
            "/api/volume/current": httpx.Response(200, json=60),
            "/api/volume/microphone/current": httpx.ReadTimeout("timed out", request=request),
            "/api/state/doa": httpx.Response(404),
        }
    )

    snapshot = await client.snapshot()

    assert snapshot.daemon_reachable is True
    assert snapshot.robot_ready is True
    assert snapshot.speaker_volume == 60
    assert snapshot.microphone_volume is None
    assert snapshot.speech_detected is None
    assert snapshot.problems == [
        "Microphone volume status is unavailable.",
        "Speech detection status is unavailable.",
    ]


@pytest.mark.asyncio
async def test_snapshot_stops_after_daemon_is_unreachable() -> None:
    """A missing daemon produces only the reachability result."""
    request = httpx.Request("GET", "http://daemon.test/api/daemon/status")
    client = status_client({"/api/daemon/status": httpx.ConnectError("offline", request=request)})

    snapshot = await client.snapshot()

    assert snapshot.to_dict() == {
        "daemon_reachable": False,
        "daemon_state": None,
        "robot_ready": None,
        "daemon_error": None,
        "backend_error": None,
        "motor_control_mode": None,
        "awake": None,
        "app_lock_state": None,
        "active_app": None,
        "speaker_volume": None,
        "microphone_volume": None,
        "speech_detected": None,
        "wlan_ip": None,
        "reachy_version": None,
        "hardware_id": None,
        "wireless_version": None,
        "battery_available": False,
        "battery_percent": None,
        "charging": None,
        "problems": ["Reachy Mini daemon is not reachable."],
    }
