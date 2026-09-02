import logging
from typing import Any

from reachy_duck.notes import list_notes, read_notes
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class ReadNotes(Tool):
    """Read all user-facing notes."""

    name = "read_notes"
    description = "Read the user's persistent notes when they ask what they have written down or saved as notes."
    parameters_schema = {
        "type": "object",
        "properties": {},
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Return the notes Markdown document and structured note entries."""
        try:
            entries = list_notes(deps.instance_path)
            notes = read_notes(deps.instance_path)
        except (OSError, UnicodeError, ValueError) as exc:
            logger.warning("Failed to read notes: %s", exc)
            return {"error": f"failed to read notes: {exc}"}

        logger.info("Tool call: read_notes")
        return {
            "notes": notes,
            "entries": [
                {
                    "id": entry.id,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    "text": entry.text,
                }
                for entry in entries
            ],
        }
