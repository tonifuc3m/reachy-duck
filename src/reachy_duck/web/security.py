"""URL validation for public web retrieval."""

from __future__ import annotations
import socket
import ipaddress
from urllib.parse import SplitResult, urlsplit
from collections.abc import Callable


class UnsafeWebUrlError(ValueError):
    """Raised when a URL could target local or private infrastructure."""


HostResolver = Callable[[str], list[str]]


def resolve_host(hostname: str) -> list[str]:
    """Resolve a hostname to addresses for SSRF validation."""
    return sorted({str(record[4][0]) for record in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)})


def _is_public_address(address: str) -> bool:
    """Return whether an address is safe for public-web retrieval."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or getattr(ip, "is_site_local", False)
    )


def validate_public_url(url: str, *, resolver: HostResolver = resolve_host) -> SplitResult:
    """Parse and validate a public HTTP(S) URL, including its resolved address."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeWebUrlError("url must be a non-empty string")
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeWebUrlError("only http and https URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeWebUrlError("URL must name a public host without credentials")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeWebUrlError("local hosts are not allowed")
    try:
        addresses = resolver(hostname)
    except OSError as exc:
        raise UnsafeWebUrlError(f"could not resolve public host: {exc}") from exc
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise UnsafeWebUrlError("local or private network targets are not allowed")
    return parsed
