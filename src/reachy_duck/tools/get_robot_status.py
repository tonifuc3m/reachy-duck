"""LLM adapter for the Reachy Mini's read-only daemon status."""

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.robot_status import get_robot_status
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class GetRobotStatus(Tool):
    """Report live local daemon status without changing robot state."""

    name = "get_robot_status"
    description = (
        "Get a live, read-only snapshot of Reachy's current daemon, backend, motor, managed app, volume, network, "
        "and version status. Use for questions about Reachy's present state; battery and charging are reported "
        "unavailable when the daemon has no official source."
    )
    parameters_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return the fresh status snapshot, safely handling expected transport failures."""
        try:
            return await get_robot_status()
        except Exception as exc:  # Defensive boundary: a tool failure must not stop conversation processing.
            logger.exception("get_robot_status failed unexpectedly")
            return {"error": f"failed to get robot status: {exc}"}
