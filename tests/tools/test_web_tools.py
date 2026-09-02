"""Tests for standard registration and failure behavior of web tools."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


def _tool_classes():
    """Import web tools after installing the minimal SDK stub needed by this test."""
    if "reachy_mini" not in sys.modules:
        reachy_mini = ModuleType("reachy_mini")
        reachy_mini.ReachyMini = type("ReachyMini", (), {})
        sys.modules["reachy_mini"] = reachy_mini
    from reachy_duck.tools.core_tools import ToolDependencies
    from reachy_duck.tools.web_search import WebSearch
    from reachy_duck.tools.fetch_web_page import FetchWebPage

    return FetchWebPage, ToolDependencies, WebSearch


@pytest.mark.asyncio
async def test_web_tools_return_structured_results_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expected retrieval failures are returned to the conversation loop."""
    from reachy_duck.web.security import UnsafeWebUrlError

    FetchWebPage, ToolDependencies, WebSearch = _tool_classes()
    deps = ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock())

    async def searched(query: str, maximum: int) -> dict[str, object]:
        return {"query": query, "results": [{"url": "https://example.com"}], "retrieved_at": "now"}

    monkeypatch.setattr("reachy_duck.tools.web_search.web_search", searched)
    assert await WebSearch()(deps, query="example") == {
        "query": "example",
        "results": [{"url": "https://example.com"}],
        "retrieved_at": "now",
    }

    async def rejected(url: str) -> dict[str, str]:
        raise UnsafeWebUrlError("local hosts are not allowed")

    monkeypatch.setattr("reachy_duck.tools.fetch_web_page.fetch_web_page", rejected)
    assert "error" in await FetchWebPage()(deps, url="http://localhost/")


def test_web_tool_schemas_are_registered_for_locked_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """The locked profile makes both read-only web tools available to the LLM."""
    from reachy_duck.config import LOCKED_PROFILE, config
    from reachy_duck.tools.core_tools import get_tools, initialize_tools

    _tool_classes()
    monkeypatch.setattr(config, "REACHY_MINI_CUSTOM_PROFILE", LOCKED_PROFILE)
    initialize_tools(force=True)
    assert {"web_search", "fetch_web_page"} <= set(get_tools())
