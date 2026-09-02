"""Tests for bounded, redacted Reachy daemon log access."""

import subprocess

import reachy_duck.log_diagnostics as logs


def test_get_recent_logs_uses_fixed_bounded_journal_command(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The only subprocess command is the allowlisted daemon journal request."""
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="normal log\n", stderr="")

    monkeypatch.setattr(logs.subprocess, "run", fake_run)

    assert logs.get_recent_logs(999)["lines"] == logs.MAX_LOG_LINES
    assert captured["command"] == [
        "journalctl",
        "-u",
        "reachy-mini-daemon.service",
        "-n",
        "300",
        "--no-pager",
        "--output=short-iso",
    ]
    assert captured["kwargs"] == {"check": False, "capture_output": True, "text": True, "timeout": 3}


def test_get_recent_logs_redacts_secrets_and_truncates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Potential credentials never reach the model and output remains bounded."""
    content = 'Authorization: Bearer secret-value\nTAVILY_API_KEY=abc\n{"access_token":"xyz"}\n' + "x" * 12_100
    monkeypatch.setattr(
        logs.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=content, stderr=""),
    )

    result = logs.get_recent_logs()

    assert "secret-value" not in result["content"]
    assert "abc" not in result["content"]
    assert "xyz" not in result["content"]
    assert result["truncated"] is True
    assert result["content"].endswith("[TRUNCATED]")


def test_diagnose_recent_logs_prioritizes_warnings_and_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Diagnostic output omits ordinary info lines while retaining useful failures."""
    monkeypatch.setattr(
        logs,
        "get_recent_logs",
        lambda: {"source": "reachy-mini-daemon", "lines": 100, "truncated": False, "content": "INFO ok\nERROR bad\n"},
    )

    assert logs.diagnose_recent_logs()["diagnostic_lines"] == "ERROR bad"


def test_get_recent_logs_hides_subprocess_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Expected journal failures return a concise safe error."""
    monkeypatch.setattr(logs.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("denied")))

    assert logs.get_recent_logs() == {
        "source": "reachy-mini-daemon",
        "lines": 100,
        "error": "Unable to read recent logs",
    }
