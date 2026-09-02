"""LLM adapter for concise public-web searches."""

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.web.search import SearchError, web_search
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class WebSearch(Tool):
    """Search the public web using the configured provider."""

    name = "web_search"
    description = "Search the live public web for current or explicitly requested online information."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Specific search terms."},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Search current public information, returning expected failures safely."""
        try:
            return await web_search(kwargs.get("query", ""), kwargs.get("max_results", 5))
        except (SearchError, TypeError, ValueError) as exc:
            logger.warning("web_search failed: %s", exc)
            return {"error": str(exc)}
