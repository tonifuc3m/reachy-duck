"""Replaceable public-web search provider backed by Brave Search."""

from __future__ import annotations
import os
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from reachy_duck.time_context import now


BRAVE_SEARCH_API_KEY_ENV = "BRAVE_SEARCH_API_KEY"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
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


class BraveSearchProvider:
    """Brave Search JSON API provider; its key never enters tool output."""

    def __init__(self, api_key: str | None = None, *, client: httpx.AsyncClient | None = None) -> None:
        """Use an explicit key/client for tests or normal environment configuration."""
        self._api_key = api_key if api_key is not None else os.getenv(BRAVE_SEARCH_API_KEY_ENV, "")
        self._client = client

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
        """Call the provider and return a bounded normalized response."""
        if not isinstance(query, str) or not query.strip():
            raise SearchError("query must be a non-empty string")
        if not self._api_key.strip():
            raise SearchError(f"web search is not configured; set {BRAVE_SEARCH_API_KEY_ENV}")
        limit = min(max(1, int(max_results)), MAX_SEARCH_RESULTS)
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": USER_AGENT})
        try:
            response = await client.get(
                BRAVE_SEARCH_URL,
                params={"q": query.strip(), "count": limit},
                headers={"X-Subscription-Token": self._api_key},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"web search failed: {exc}") from exc
        finally:
            if own_client:
                await client.aclose()
        return parse_brave_search_response(payload, query=query.strip(), max_results=limit)


def parse_brave_search_response(payload: object, *, query: str, max_results: int) -> dict[str, Any]:
    """Normalize Brave's response while keeping only bounded LLM-facing fields."""
    if not isinstance(payload, dict):
        raise SearchError("search provider returned malformed data")
    web = payload.get("web")
    raw_results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(raw_results, list):
        raise SearchError("search provider returned no result list")
    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title, url, description = item.get("title"), item.get("url"), item.get("description", "")
        if not isinstance(title, str) or not isinstance(url, str) or not title.strip() or not url.strip():
            continue
        hostname = urlsplit(url).hostname
        results.append(
            {
                "title": title.strip()[:300],
                "url": url.strip(),
                "snippet": description.strip()[:600] if isinstance(description, str) else "",
                "domain": hostname or "",
            }
        )
        if len(results) == max_results:
            break
    return {"query": query, "results": results, "retrieved_at": now().isoformat(timespec="seconds")}


async def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    """Search the public web using the configured replaceable provider."""
    return await BraveSearchProvider().search(query, max_results)
