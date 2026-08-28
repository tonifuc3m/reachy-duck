import logging
from typing import Any

from reachy_duck.notes import read_notes
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
        """Return the notes Markdown document."""
        try:
            notes = read_notes(deps.instance_path)
        except (OSError, UnicodeError) as exc:
            logger.warning("Failed to read notes: %s", exc)
            return {"error": f"failed to read notes: {exc}"}

        logger.info("Tool call: read_notes")
        return {"notes": notes}
