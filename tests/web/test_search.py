"""Tests for the bounded Brave Search provider."""

import httpx
import pytest

from reachy_duck.web.search import SearchError, BraveSearchProvider, parse_brave_search_response


def test_parse_brave_results_keeps_concise_source_metadata() -> None:
    """Provider data is normalized to the LLM-facing shape."""
    result = parse_brave_search_response(
        {
            "web": {
                "results": [
                    {
                        "title": "Official docs",
                        "url": "https://docs.example.com/page",
                        "description": "A short description.",
                    }
                ]
            }
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
async def test_brave_provider_sends_key_in_request_not_result() -> None:
    """The credential stays inside the HTTP request implementation."""
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"web": {"results": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BraveSearchProvider("secret-key", client=client).search("Reachy", 99)

    assert seen_headers["x-subscription-token"] == "secret-key"
    assert result["query"] == "Reachy"
    assert result["results"] == []
    assert "retrieved_at" in result


@pytest.mark.asyncio
async def test_missing_key_and_malformed_response_fail_clearly() -> None:
    """Missing credentials and unexpected provider payloads do not fabricate results."""
    with pytest.raises(SearchError, match="BRAVE_SEARCH_API_KEY"):
        await BraveSearchProvider("").search("Reachy")
    with pytest.raises(SearchError, match="malformed"):
        parse_brave_search_response([], query="Reachy", max_results=5)
