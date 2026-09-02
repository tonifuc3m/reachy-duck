"""LLM adapter for editing one identified user-facing note."""

import logging
from typing import Any

from reachy_duck.notes import edit_note
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class EditNote(Tool):
    """Replace or extend one user-facing note."""

    name = "edit_note"
    description = (
        "Update one note after using read_notes to identify it. Use replace to change the full text and append to "
        "add text after the existing note. If several notes could match, ask the user a short clarification first."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "ID from a current read_notes result."},
            "text": {"type": "string", "description": "Complete replacement text or text to append."},
            "mode": {"type": "string", "enum": ["replace", "append"], "default": "replace"},
        },
        "required": ["note_id", "text"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Persist one note update."""
        note_id = kwargs.get("note_id")
        text = kwargs.get("text")
        mode = kwargs.get("mode", "replace")
        if not isinstance(note_id, str) or not note_id.strip():
            return {"error": "note_id must be a non-empty string"}
        if not isinstance(text, str) or not text.strip():
            return {"error": "text must be a non-empty string"}
        if mode not in {"replace", "append"}:
            return {"error": "mode must be 'replace' or 'append'"}
        try:
            updated = edit_note(note_id, text, mode, instance_path=deps.instance_path)
        except (OSError, UnicodeError, ValueError) as exc:
            logger.warning("Failed to edit note: %s", exc)
            return {"error": f"failed to edit note: {exc}"}
        if updated is None:
            return {"error": "note not found"}
        logger.info("Tool call: edit_note id=%s mode=%s", updated.id, mode)
        return {
            "updated": {
                "id": updated.id,
                "text": updated.text,
                "mode": mode,
                "updated_at": updated.updated_at,
            }
        }
