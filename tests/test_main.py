"""Tests for app-level runtime behavior."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import reachy_duck.main as main_mod


def test_inactivity_timeout_thread_goes_to_sleep() -> None:
    """The watchdog should use the shared sleep shutdown path once activity is too old."""
    stream_manager = SimpleNamespace(seconds_since_activity=lambda: 10.0, close=MagicMock())
    go_to_sleep = MagicMock(return_value={"status": "sleeping"})

    thread = main_mod._start_inactivity_timeout_thread(
        timeout_minutes=0.0001,
        stream_manager=stream_manager,
        logger=MagicMock(),
        app_stop_event=threading.Event(),
        go_to_sleep=go_to_sleep,
    )

    thread.join(timeout=1.0)
    assert not thread.is_alive()
    go_to_sleep.assert_called_once_with()
    stream_manager.close.assert_not_called()


def test_inactivity_timeout_thread_closes_stream_manager_without_sleep_callback() -> None:
    """The watchdog should still close the stream when no sleep callback is available."""
    stream_manager = SimpleNamespace(seconds_since_activity=lambda: 10.0, close=MagicMock())

    thread = main_mod._start_inactivity_timeout_thread(
        timeout_minutes=0.0001,
        stream_manager=stream_manager,
        logger=MagicMock(),
        app_stop_event=threading.Event(),
    )

    thread.join(timeout=1.0)
    assert not thread.is_alive()
    stream_manager.close.assert_called_once_with()


def test_wireless_launcher_uses_persistent_user_data(tmp_path, monkeypatch) -> None:
    """The managed app should keep state outside its replaceable installation."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(main_mod, "parse_args", lambda: (SimpleNamespace(), []))
    run = MagicMock()
    monkeypatch.setattr(main_mod, "run", run)

    app = object.__new__(main_mod.ReachyDuck)
    app.settings_app = None
    robot = MagicMock()
    stop_event = threading.Event()
    app.run(robot, stop_event)

    run.assert_called_once_with(
        SimpleNamespace(),
        robot=robot,
        app_stop_event=stop_event,
        settings_app=None,
        instance_path=str(tmp_path / "reachy_duck"),
    )
