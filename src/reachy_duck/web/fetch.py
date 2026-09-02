"""Safe, bounded fetching and plain-text extraction for public HTML pages."""

from __future__ import annotations
import re
from html import unescape
from typing import Any
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from reachy_duck.time_context import now
from reachy_duck.web.security import HostResolver, UnsafeWebUrlError, resolve_host, validate_public_url


REQUEST_TIMEOUT_S = 10.0
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_000_000
MAX_EXTRACTED_TEXT_CHARS = 12_000
USER_AGENT = "ReachyDuck/1.0 (+https://github.com/pollen-robotics/reachy-mini)"
_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form"}


class WebFetchError(RuntimeError):
    """Raised for expected public-page retrieval failures."""


class _TextExtractor(HTMLParser):
    """Small dependency-free extractor for useful text from ordinary HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "pre", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if not self._skip_depth:
            self.parts.append(data)

    def extracted(self) -> tuple[str, str]:
        title = _normalise_text(" ".join(self.title_parts))
        content = "\n".join(
            line for line in (_normalise_text(line) for line in "".join(self.parts).splitlines()) if line
        )
        return title, content


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_html_text(html: str) -> tuple[str, str]:
    """Return title and readable body text, excluding obvious page chrome."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.extracted()


class WebFetcher:
    """Fetch public text pages with URL, redirect, and memory limits."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        resolver: HostResolver = resolve_host,
    ) -> None:
        """Use injected HTTP and DNS dependencies when testing."""
        self._client = client
        self._resolver = resolver

    async def fetch(self, url: str) -> dict[str, Any]:
        """Retrieve one validated public page without following unsafe redirects."""
        current_url = url
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/xhtml+xml"},
        )
        try:
            for _ in range(MAX_REDIRECTS + 1):
                validate_public_url(current_url, resolver=self._resolver)
                try:
                    async with client.stream("GET", current_url, follow_redirects=False) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise WebFetchError("page redirected without a destination")
                            current_url = urljoin(str(response.url), location)
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if "pdf" in content_type:
                            raise WebFetchError("PDF documents are unsupported in web browsing v1")
                        if not any(
                            kind in content_type for kind in ("text/html", "text/plain", "application/xhtml+xml")
                        ):
                            raise WebFetchError("this page is not a supported HTML or text document")
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                            raise WebFetchError("page is too large to read safely")
                        body = await _read_bounded(response)
                        return _page_payload(
                            body.decode(response.encoding or "utf-8", errors="replace"), str(response.url)
                        )
                except UnsafeWebUrlError:
                    raise
                except (httpx.HTTPError, ValueError) as exc:
                    raise WebFetchError(f"could not fetch page: {exc}") from exc
            raise WebFetchError("page exceeded the redirect limit")
        finally:
            if own_client:
                await client.aclose()


async def _read_bounded(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes(chunk_size=8192):
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise WebFetchError("page is too large to read safely")
        chunks.append(chunk)
    return b"".join(chunks)


def _page_payload(raw_text: str, final_url: str) -> dict[str, Any]:
    title, content = extract_html_text(raw_text)
    truncated = len(content) > MAX_EXTRACTED_TEXT_CHARS
    if truncated:
        content = content[:MAX_EXTRACTED_TEXT_CHARS].rstrip() + "\n\n[Content truncated for safety.]"
    return {
        "title": title or final_url,
        "url": final_url,
        "content": content,
        "retrieved_at": now().isoformat(timespec="seconds"),
        "truncated": truncated,
        "untrusted_content": True,
    }


async def fetch_web_page(url: str) -> dict[str, Any]:
    """Fetch bounded readable content from one public webpage."""
    return await WebFetcher().fetch(url)
