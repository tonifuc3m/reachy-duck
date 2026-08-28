import logging
from typing import Any

from reachy_duck.memory import remember
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class Remember(Tool):
    """Save one long-term internal memory entry."""

    name = "remember"
    description = (
        "Save one stable fact, preference, or project detail to long-term internal memory so it is available in future "
        "conversations. Use this when the user explicitly asks you to remember something. Do not use it for temporary "
        "reminders or user-facing notes."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The concise information to retain, such as 'This project uses pytest'.",
            },
        },
        "required": ["text"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Save one memory fact."""
        text = kwargs.get("text")
        if not isinstance(text, str) or not text.strip():
            logger.warning("remember: empty text")
            return {"error": "text must be a non-empty string"}

        try:
            stored = remember(text, instance_path=deps.instance_path)
        except (OSError, UnicodeError) as exc:
            logger.warning("Failed to save memory: %s", exc)
            return {"error": f"failed to save memory: {exc}"}
        if stored is None:
            return {"error": "text was empty; nothing was saved"}

        logger.info("Tool call: remember text=%s", stored[:120])
        return {"saved": stored}
