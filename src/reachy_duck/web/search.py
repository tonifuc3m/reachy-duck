"""Replaceable public-web search provider backed by Tavily Search."""

from __future__ import annotations
import os
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from reachy_duck.time_context import now


TAVILY_API_KEY_ENV = "TAVILY_API_KEY"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
MAX_SEARCH_RESULTS = 10
REQUEST_TIMEOUT_S = 8.0
USER_AGENT = "ReachyDuck/1.0 (+https://github.com/pollen-robotics/reachy-mini)"


class SearchError(RuntimeError):
    """Raised when a search provider cannot return usable results."""


class SearchProvider(Protocol):
    """Minimal abstraction for a programmatic web-search backend."""

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
        """Return concise public search results."""
        ...


class TavilySearchProvider:
    """Tavily Search JSON API provider; its key never enters tool output."""

    def __init__(self, api_key: str | None = None, *, client: httpx.AsyncClient | None = None) -> None:
        """Use an explicit key/client for tests or normal environment configuration."""
        self._api_key = api_key if api_key is not None else os.getenv(TAVILY_API_KEY_ENV, "")
        self._client = client

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
        """Call the provider and return a bounded normalized response."""
        if not isinstance(query, str) or not query.strip():
            raise SearchError("query must be a non-empty string")
        if not self._api_key.strip():
            raise SearchError(f"web search is not configured; set {TAVILY_API_KEY_ENV}")
        limit = min(max(1, int(max_results)), MAX_SEARCH_RESULTS)
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": USER_AGENT})
        try:
            response = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "query": query.strip(),
                    "max_results": limit,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                    "safe_search": True,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"web search failed: {exc}") from exc
        finally:
            if own_client:
                await client.aclose()
        return parse_tavily_search_response(payload, query=query.strip(), max_results=limit)


def parse_tavily_search_response(payload: object, *, query: str, max_results: int) -> dict[str, Any]:
    """Normalize Tavily's response while keeping only bounded LLM-facing fields."""
    if not isinstance(payload, dict):
        raise SearchError("search provider returned malformed data")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise SearchError("search provider returned no result list")
    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title, url, content = item.get("title"), item.get("url"), item.get("content", "")
        if not isinstance(title, str) or not isinstance(url, str) or not title.strip() or not url.strip():
            continue
        hostname = urlsplit(url).hostname
        results.append(
            {
                "title": title.strip()[:300],
                "url": url.strip(),
                "snippet": content.strip()[:600] if isinstance(content, str) else "",
                "domain": hostname or "",
            }
        )
        if len(results) == max_results:
            break
    return {"query": query, "results": results, "retrieved_at": now().isoformat(timespec="seconds")}


async def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    """Search the public web using the configured replaceable provider."""
    return await TavilySearchProvider().search(query, max_results)
