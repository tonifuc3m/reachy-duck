"""LLM adapter for bounded public webpage reading."""

from __future__ import annotations
import logging
from typing import Any

from reachy_duck.web.fetch import WebFetchError, fetch_web_page
from reachy_duck.web.security import UnsafeWebUrlError
from reachy_duck.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class FetchWebPage(Tool):
    """Read one public HTML or text page after URL security validation."""

    name = "fetch_web_page"
    description = "Fetch a public HTML/text page and return bounded readable text. Read relevant search results before answering material claims."
    parameters_schema = {
        "type": "object",
        "properties": {"url": {"type": "string", "format": "uri", "description": "Public http(s) URL to read."}},
        "required": ["url"],
        "additionalProperties": False,
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        """Read a public page, returning expected failures safely."""
        try:
            return await fetch_web_page(kwargs.get("url", ""))
        except (UnsafeWebUrlError, WebFetchError, TypeError, ValueError) as exc:
            logger.warning("fetch_web_page failed: %s", exc)
            return {"error": str(exc)}
