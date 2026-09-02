"""LLM adapter for deleting one identified user-facing note."""

import logging
from typing import Any

from reachy_duck.notes import delete_note
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class DeleteNote(Tool):
    """Remove one user-facing note."""

    name = "delete_note"
    description = (
        "Delete one note after using read_notes to identify it. Ask a short clarification if the requested note is "
        "ambiguous; do not use this for bulk deletion."
    )
    parameters_schema = {
        "type": "object",
        "properties": {"note_id": {"type": "string", "description": "ID from a current read_notes result."}},
        "required": ["note_id"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Persist one note deletion."""
        note_id = kwargs.get("note_id")
        if not isinstance(note_id, str) or not note_id.strip():
            return {"error": "note_id must be a non-empty string"}
        try:
            deleted = delete_note(note_id, instance_path=deps.instance_path)
        except (OSError, UnicodeError, ValueError) as exc:
            logger.warning("Failed to delete note: %s", exc)
            return {"error": f"failed to delete note: {exc}"}
        if deleted is None:
            return {"error": "note not found"}
        logger.info("Tool call: delete_note id=%s", deleted.id)
        return {"deleted": {"id": deleted.id, "text": deleted.text}}
