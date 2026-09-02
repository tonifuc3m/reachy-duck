"""LLM adapter for safe, bounded Reachy log diagnosis."""

from typing import Any

from reachy_duck.log_diagnostics import diagnose_recent_logs
from reachy_duck.tools.core_tools import Tool, ToolDependencies


class DiagnoseRecentLogs(Tool):
    """Return diagnostic log lines for a concise explanation."""

    name = "diagnose_recent_logs"
    description = "Inspect recent redacted logs when the user asks why something failed or whether there are errors."
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return warnings and errors from the fixed daemon journal."""
        return diagnose_recent_logs()
