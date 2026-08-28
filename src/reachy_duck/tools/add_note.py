import logging
from typing import Any

from reachy_duck.notes import add_note
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class AddNote(Tool):
    """Append one timestamped user-facing note."""

    name = "add_note"
    description = (
        "Write information to the user's persistent notes when they ask you to write something down, make a note, "
        "or save a reminder. Use remember instead for stable background context about the user or project."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The note text to write.",
            },
        },
        "required": ["text"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Append one note."""
        text = kwargs.get("text")
        if not isinstance(text, str) or not text.strip():
            logger.warning("add_note: empty text")
            return {"error": "text must be a non-empty string"}

        try:
            stored = add_note(text, instance_path=deps.instance_path)
        except (OSError, UnicodeError) as exc:
            logger.warning("Failed to add note: %s", exc)
            return {"error": f"failed to add note: {exc}"}
        if stored is None:
            return {"error": "text was empty; nothing was saved"}

        logger.info("Tool call: add_note text=%s", stored[:120])
        return {"saved": stored}
