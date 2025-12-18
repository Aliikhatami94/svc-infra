"""
WebSocket client for connecting to external services.

Provides:
- WebSocketClient: Async WebSocket client with context manager support
- websocket_connect: Context manager/async iterator for connections

Example:
    from svc_infra.websocket import WebSocketClient

    async with WebSocketClient("wss://api.example.com") as ws:
        await ws.send_json({"type": "hello"})
        async for message in ws:
            print(message)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from websockets.typing import Subprotocol

from .config import WebSocketConfig, get_default_config
from .exceptions import ConnectionClosedError, ConnectionFailedError, WebSocketError

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    Async WebSocket client for connecting to external services.

    Features:
    - Async context manager support
    - Auto-reconnection with exponential backoff (via websocket_connect)
    - Configurable ping/pong keepalive
    - Send text, bytes, or JSON
    - Async iterator for receiving messages

    Example:
        async with WebSocketClient("wss://api.example.com") as ws:
            await ws.send_json({"type": "hello"})
            async for message in ws:
                print(message)

    Args:
        url: WebSocket URL (ws:// or wss://)
        config: WebSocket configuration (timeouts, ping/pong, etc.)
        headers: Additional HTTP headers for the handshake
        subprotocols: List of subprotocols to negotiate
    """

    def __init__(
        self,
        url: str,
        *,
        config: WebSocketConfig | None = None,
        headers: dict[str, str] | None = None,
        subprotocols: list[str] | None = None,
    ):
        self.url = url
        self.config = config or get_default_config()
        self.headers = headers or {}
        self.subprotocols = subprotocols
        self._connection: ClientConnection | None = None
        self._closed = False

    async def __aenter__(self) -> WebSocketClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Establish WebSocket connection.

        Raises:
            ConnectionFailedError: If connection cannot be established
        """
        try:
            # Cast subprotocols to Subprotocol type for type safety
            subprotocols_typed: list[Subprotocol] | None = None
            if self.subprotocols:
                subprotocols_typed = [Subprotocol(s) for s in self.subprotocols]

            self._connection = await connect(
                self.url,
                additional_headers=self.headers,
                subprotocols=subprotocols_typed,
                open_timeout=self.config.open_timeout,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
                close_timeout=self.config.close_timeout,
                max_size=self.config.max_message_size,
                max_queue=self.config.max_queue_size,
            )
            self._closed = False
            logger.debug("Connected to %s", self.url)
        except Exception as e:
            raise ConnectionFailedError(f"Failed to connect to {self.url}: {e}") from e

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection gracefully.

        Args:
            code: WebSocket close code (default: 1000 = normal closure)
            reason: Close reason message
        """
        if self._connection and not self._closed:
            self._closed = True
            try:
                await self._connection.close(code=code, reason=reason)
                logger.debug("Closed connection to %s", self.url)
            except Exception as e:
                logger.warning("Error closing connection to %s: %s", self.url, e)

    async def send(self, data: str | bytes) -> None:
        """Send text or binary message.

        Args:
            data: Message content (str for text, bytes for binary)

        Raises:
            WebSocketError: If not connected
            ConnectionClosedError: If connection is closed
        """
        if not self._connection:
            raise WebSocketError("Not connected")
        try:
            await self._connection.send(data)
        except ConnectionClosedOK:
            raise ConnectionClosedError(1000, "Normal closure")
        except ConnectionClosed as e:
            raise ConnectionClosedError(e.code, e.reason) from e

    async def send_json(self, data: Any) -> None:
        """Send JSON-serialized message.

        Args:
            data: Object to serialize and send

        Raises:
            WebSocketError: If not connected
            ConnectionClosedError: If connection is closed
            TypeError/ValueError: If data cannot be serialized
        """
        await self.send(json.dumps(data))

    async def recv(self) -> str | bytes:
        """Receive next message.

        Returns:
            Message content (str for text frames, bytes for binary)

        Raises:
            WebSocketError: If not connected
            ConnectionClosedError: If connection is closed
        """
        if not self._connection:
            raise WebSocketError("Not connected")
        try:
            result = await self._connection.recv()
            return str(result) if isinstance(result, str) else bytes(result)
        except ConnectionClosedOK:
            raise ConnectionClosedError(1000, "Normal closure")
        except ConnectionClosed as e:
            raise ConnectionClosedError(e.code, e.reason) from e

    async def recv_json(self) -> Any:
        """Receive and parse JSON message.

        Returns:
            Parsed JSON object

        Raises:
            WebSocketError: If not connected
            ConnectionClosedError: If connection is closed
            json.JSONDecodeError: If message is not valid JSON
        """
        data = await self.recv()
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)

    async def __aiter__(self) -> AsyncIterator[str | bytes]:
        """Iterate over incoming messages until closed.

        Yields:
            Message content (str for text, bytes for binary)

        Raises:
            ConnectionClosedError: If connection is closed abnormally
        """
        if not self._connection:
            raise WebSocketError("Not connected")
        try:
            async for message in self._connection:
                yield message
        except ConnectionClosedOK:
            return
        except ConnectionClosed as e:
            raise ConnectionClosedError(e.code, e.reason) from e

    @property
    def is_connected(self) -> bool:
        """Check if connection is open."""
        return self._connection is not None and not self._closed

    @property
    def latency(self) -> float:
        """Connection latency in seconds (from ping/pong).

        Returns 0.0 if not connected or no ping has been sent.
        """
        return self._connection.latency if self._connection else 0.0


@asynccontextmanager
async def websocket_connect(
    url: str,
    *,
    config: WebSocketConfig | None = None,
    headers: dict[str, str] | None = None,
    auto_reconnect: bool = False,
) -> AsyncIterator[WebSocketClient]:
    """
    Context manager for WebSocket connections.

    Args:
        url: WebSocket URL (ws:// or wss://)
        config: WebSocket configuration
        headers: Additional HTTP headers
        auto_reconnect: If True, auto-reconnects on connection loss

    Yields:
        WebSocketClient instance

    Example (simple):
        async with websocket_connect("wss://api.example.com") as ws:
            await ws.send_json({"hello": "world"})

    Example (with auto-reconnect):
        # Note: with auto_reconnect=True, this becomes an async iterator
        async for ws in websocket_connect(url, auto_reconnect=True):
            try:
                async for msg in ws:
                    process(msg)
            except ConnectionClosedError:
                continue  # Will reconnect
    """
    if auto_reconnect:
        # Use websockets' built-in reconnection iterator
        cfg = config or get_default_config()
        async for connection in connect(
            url,
            additional_headers=headers or {},
            open_timeout=cfg.open_timeout,
            ping_interval=cfg.ping_interval,
            ping_timeout=cfg.ping_timeout,
            close_timeout=cfg.close_timeout,
            max_size=cfg.max_message_size,
        ):
            client = WebSocketClient(url, config=config, headers=headers)
            client._connection = connection
            client._closed = False
            yield client
    else:
        client = WebSocketClient(url, config=config, headers=headers)
        await client.connect()
        try:
            yield client
        finally:
            await client.close()
