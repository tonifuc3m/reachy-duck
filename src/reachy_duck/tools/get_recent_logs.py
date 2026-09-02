"""LLM adapters for safe, bounded Reachy log diagnostics."""

from typing import Any

from reachy_duck.log_diagnostics import get_recent_logs, diagnose_recent_logs
from reachy_duck.tools.core_tools import Tool, ToolDependencies


class GetRecentLogs(Tool):
    """Read a bounded redacted excerpt of Reachy's daemon logs."""

    name = "get_recent_logs"
    description = "Read a small, redacted excerpt of recent Reachy Duck and daemon logs for diagnosis."
    parameters_schema = {
        "type": "object",
        "properties": {"lines": {"type": "integer", "minimum": 1, "maximum": 300, "default": 100}},
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return fixed-source logs without exposing paths or shell access."""
        return get_recent_logs(kwargs.get("lines", 100))


class DiagnoseRecentLogs(Tool):
    """Return diagnostic log lines for a concise explanation."""

    name = "diagnose_recent_logs"
    description = "Inspect recent redacted logs when the user asks why something failed or whether there are errors."
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return warnings and errors from the fixed daemon journal."""
        return diagnose_recent_logs()
