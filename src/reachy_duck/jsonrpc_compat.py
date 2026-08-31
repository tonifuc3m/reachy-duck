"""Optional JSON-RPC support for SDK versions used by Reachy Mini Wireless."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any
from collections.abc import Callable


logger = logging.getLogger(__name__)
__all__ = ["JsonRpcError", "JsonRpcServer"]

if TYPE_CHECKING:
    from reachy_mini.io.jsonrpc import JsonRpcError
    from reachy_mini.apps.jsonrpc_server import JsonRpcServer
else:
    try:
        from reachy_mini.io.jsonrpc import JsonRpcError
        from reachy_mini.apps.jsonrpc_server import JsonRpcServer

        JSONRPC_AVAILABLE = True
    except ModuleNotFoundError:
        JSONRPC_AVAILABLE = False

        class JsonRpcError(RuntimeError):
            """Compatibility error used when the Wireless SDK has no JSON-RPC module."""

            def __init__(
                self,
                message: str,
                *,
                reason: str | None = None,
                code: int | None = None,
                data: Any = None,
            ) -> None:
                """Store the JSON-RPC-shaped fields used by existing route handlers."""
                super().__init__(message)
                self.reason = reason
                self.code = code
                self.data = data

        class JsonRpcServer:
            """No-op server for SDK 1.9, where browser controls are unavailable."""

            def __init__(self) -> None:
                """Record that only the unsupported browser control surface is disabled."""
                logger.warning("Reachy Mini SDK has no JSON-RPC support; browser controls are disabled")

            def method(self, _name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                """Return the decorated handler unchanged."""
                return lambda handler: handler

            def register(self, _name: str, _handler: Callable[..., Any]) -> None:
                """Ignore named browser handlers when no JSON-RPC transport exists."""

            def broadcast_threadsafe(self, _name: str, _params: dict[str, Any]) -> None:
                """Ignore browser notifications when no JSON-RPC transport exists."""

            def mount(self, _app: Any) -> None:
                """Leave the legacy browser control route unmounted."""
