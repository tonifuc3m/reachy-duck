"""LLM adapter for lexical note searching."""

import logging
from typing import Any

from reachy_duck.notes import search_notes
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class SearchNotes(Tool):
    """Find matching timestamped note entries."""

    name = "search_notes"
    description = "Search the user's persistent notes for a word or phrase without reading every note aloud."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Word or phrase to find in the notes."},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": ["query"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Search persistent notes, returning a bounded result set."""
        query = kwargs.get("query")
        max_results = kwargs.get("max_results", 5)
        if not isinstance(query, str) or not query.strip():
            return {"error": "query must be a non-empty string"}
        if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 20:
            return {"error": "max_results must be an integer between 1 and 20"}
        try:
            result = search_notes(query, max_results, instance_path=deps.instance_path)
        except (OSError, UnicodeError) as exc:
            logger.warning("Failed to search notes: %s", exc)
            return {"error": "failed to search notes"}
        logger.info("Tool call: search_notes query=%s", query[:120])
        return result
