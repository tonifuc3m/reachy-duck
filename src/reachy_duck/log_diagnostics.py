"""Bounded, redacted diagnostics from the Reachy daemon journal."""

from __future__ import annotations
import re
import subprocess
from typing import Any


DEFAULT_LOG_LINES = 100
MAX_LOG_LINES = 300
MAX_LOG_CHARACTERS = 12_000
JOURNAL_TIMEOUT_SECONDS = 3
DAEMON_UNIT = "reachy-mini-daemon.service"

_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+")
_ASSIGNMENT_PATTERN = re.compile(r"(?im)\b([A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\s*=\s*)[^\s#]+")
_JSON_SECRET_PATTERN = re.compile(
    r'(?i)("(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"\s*:\s*")[^"]*'
)
_DIAGNOSTIC_PATTERN = re.compile(r"(?i)\b(error|warning|exception|traceback|http [45]\d\d)\b")


def get_recent_logs(lines: int = DEFAULT_LOG_LINES) -> dict[str, Any]:
    """Return a bounded, redacted excerpt of the fixed Reachy daemon journal."""
    line_limit = _bounded_line_count(lines)
    command = [
        "journalctl",
        "-u",
        DAEMON_UNIT,
        "-n",
        str(line_limit),
        "--no-pager",
        "--output=short-iso",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=JOURNAL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"source": "reachy-mini-daemon", "lines": line_limit, "error": "Unable to read recent logs"}

    if result.returncode != 0:
        return {"source": "reachy-mini-daemon", "lines": line_limit, "error": "Unable to read recent logs"}

    content, truncated = _bounded_redacted_content(result.stdout)
    return {
        "source": "reachy-mini-daemon",
        "lines": line_limit,
        "truncated": truncated,
        "content": content,
    }


def diagnose_recent_logs() -> dict[str, Any]:
    """Return recent diagnostic lines for the LLM to explain as untrusted data."""
    result = get_recent_logs()
    content = result.get("content")
    if not isinstance(content, str):
        return result
    diagnostic_lines = [line for line in content.splitlines() if _DIAGNOSTIC_PATTERN.search(line)]
    return {**result, "diagnostic_lines": "\n".join(diagnostic_lines)}


def _bounded_line_count(lines: int) -> int:
    """Apply a fixed upper bound without accepting non-integer values."""
    if not isinstance(lines, int) or isinstance(lines, bool):
        return DEFAULT_LOG_LINES
    return min(max(lines, 1), MAX_LOG_LINES)


def _bounded_redacted_content(content: str) -> tuple[str, bool]:
    """Redact common secret forms and cap output sent to the model."""
    redacted = _BEARER_PATTERN.sub(r"\1[REDACTED]", content)
    redacted = _ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", redacted)
    redacted = _JSON_SECRET_PATTERN.sub(r"\1[REDACTED]", redacted)
    if len(redacted) <= MAX_LOG_CHARACTERS:
        return redacted, False
    return f"{redacted[:MAX_LOG_CHARACTERS]}\n[TRUNCATED]", True
