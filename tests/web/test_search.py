"""Tests for the bounded Tavily Search provider."""

import json

import httpx
import pytest

from reachy_duck.web.search import SearchError, TavilySearchProvider, parse_tavily_search_response


def test_parse_tavily_results_keeps_concise_source_metadata() -> None:
    """Provider data is normalized to the LLM-facing shape."""
    result = parse_tavily_search_response(
        {
            "results": [
                {
                    "title": "Official docs",
                    "url": "https://docs.example.com/page",
                    "content": "A short description.",
                }
            ]
        },
        query="example docs",
        max_results=5,
    )

    assert result["query"] == "example docs"
    assert result["results"] == [
        {
            "title": "Official docs",
            "url": "https://docs.example.com/page",
            "snippet": "A short description.",
            "domain": "docs.example.com",
        }
    ]
    assert "retrieved_at" in result


@pytest.mark.asyncio
async def test_tavily_provider_sends_key_in_request_not_result() -> None:
    """The credential stays inside the HTTP request implementation."""
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        assert request.method == "POST"
        assert request.url == "https://api.tavily.com/search"
        assert json.loads(request.content) == {
            "query": "Reachy",
            "max_results": 10,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "safe_search": True,
        }
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TavilySearchProvider("secret-key", client=client).search("Reachy", 99)

    assert seen_headers["authorization"] == "Bearer secret-key"
    assert result["query"] == "Reachy"
    assert result["results"] == []
    assert "retrieved_at" in result


@pytest.mark.asyncio
async def test_missing_key_and_malformed_response_fail_clearly() -> None:
    """Missing credentials and unexpected provider payloads do not fabricate results."""
    with pytest.raises(SearchError, match="TAVILY_API_KEY"):
        await TavilySearchProvider("").search("Reachy")
    with pytest.raises(SearchError, match="malformed"):
        parse_tavily_search_response([], query="Reachy", max_results=5)
