"""Tests for WebSocketClient.

Tests connection lifecycle, message handling, error handling,
and context manager usage.
"""

import pytest

pytestmark = pytest.mark.websocket
from unittest.mock import AsyncMock, MagicMock, patch

from svc_infra.websocket.client import WebSocketClient
from svc_infra.websocket.config import WebSocketConfig
from svc_infra.websocket.exceptions import (
    ConnectionClosedError,
    ConnectionFailedError,
    WebSocketError,
)


class TestWebSocketClientInit:
    """Test WebSocketClient initialization."""

    def test_init_with_url(self):
        """Client initializes with URL."""
        client = WebSocketClient("wss://example.com/ws")
        assert client.url == "wss://example.com/ws"
        assert client._connection is None
        assert client._closed is False

    def test_init_with_config(self):
        """Client initializes with custom config."""
        config = WebSocketConfig(
            ping_interval=10.0,
            ping_timeout=5.0,
            max_message_size=1024,
        )
        client = WebSocketClient("wss://example.com/ws", config=config)
        assert client.config.ping_interval == 10.0
        assert client.config.ping_timeout == 5.0
        assert client.config.max_message_size == 1024

    def test_init_with_headers(self):
        """Client initializes with custom headers."""
        headers = {"Authorization": "Bearer token123"}
        client = WebSocketClient("wss://example.com/ws", headers=headers)
        assert client.headers == headers

    def test_init_with_subprotocols(self):
        """Client initializes with subprotocols."""
        subprotocols = ["graphql-ws", "graphql-transport-ws"]
        client = WebSocketClient("wss://example.com/ws", subprotocols=subprotocols)
        assert client.subprotocols == subprotocols

    def test_init_defaults(self):
        """Client has sensible defaults."""
        client = WebSocketClient("wss://example.com/ws")
        assert client.headers == {}
        assert client.subprotocols is None
        assert client.config is not None


class TestWebSocketClientConnect:
    """Test WebSocketClient connect behavior."""

    @pytest.mark.asyncio
    async def test_connect_sets_connection(self):
        """connect() establishes connection."""
        client = WebSocketClient("wss://example.com/ws")

        mock_connection = MagicMock()

        # websockets.connect returns a coroutine, so we need to mock it properly
        async def mock_connect(*args, **kwargs):
            return mock_connection

        with patch("svc_infra.websocket.client.connect", side_effect=mock_connect):
            await client.connect()

            assert client._connection is mock_connection
            assert client._closed is False

    @pytest.mark.asyncio
    async def test_connect_raises_on_failure(self):
        """connect() raises ConnectionFailedError on failure."""
        client = WebSocketClient("wss://example.com/ws")

        async def mock_connect_fail(*args, **kwargs):
            raise Exception("Connection refused")

        with patch("svc_infra.websocket.client.connect", side_effect=mock_connect_fail):
            with pytest.raises(ConnectionFailedError):
                await client.connect()


class TestWebSocketClientClose:
    """Test WebSocketClient close behavior."""

    @pytest.mark.asyncio
    async def test_close_calls_connection_close(self):
        """close() closes the connection."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        client._connection = mock_connection

        await client.close()

        mock_connection.close.assert_called_once()
        assert client._closed is True

    @pytest.mark.asyncio
    async def test_close_without_connection(self):
        """close() is safe when not connected."""
        client = WebSocketClient("wss://example.com/ws")

        # Should not raise
        await client.close()

    @pytest.mark.asyncio
    async def test_close_with_code_and_reason(self):
        """close() accepts code and reason."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        client._connection = mock_connection

        await client.close(code=1001, reason="Going away")

        mock_connection.close.assert_called_once_with(code=1001, reason="Going away")


class TestWebSocketClientMessaging:
    """Test WebSocketClient send and receive methods."""

    @pytest.mark.asyncio
    async def test_send_text(self):
        """send() sends text message."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        client._connection = mock_connection

        await client.send("hello")

        mock_connection.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_bytes(self):
        """send() sends binary message."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        client._connection = mock_connection

        await client.send(b"binary data")

        mock_connection.send.assert_called_once_with(b"binary data")

    @pytest.mark.asyncio
    async def test_send_requires_connection(self):
        """send() raises when not connected."""
        client = WebSocketClient("wss://example.com/ws")

        with pytest.raises(WebSocketError, match="Not connected"):
            await client.send("hello")

    @pytest.mark.asyncio
    async def test_send_json(self):
        """send_json() serializes and sends JSON."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        client._connection = mock_connection

        await client.send_json({"type": "message", "data": "hello"})

        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"type": "message"' in sent_data or '"type":"message"' in sent_data

    @pytest.mark.asyncio
    async def test_recv(self):
        """recv() receives message."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        mock_connection.recv.return_value = "hello"
        client._connection = mock_connection

        result = await client.recv()

        assert result == "hello"

    @pytest.mark.asyncio
    async def test_recv_requires_connection(self):
        """recv() raises when not connected."""
        client = WebSocketClient("wss://example.com/ws")

        with pytest.raises(WebSocketError, match="Not connected"):
            await client.recv()

    @pytest.mark.asyncio
    async def test_recv_json(self):
        """recv_json() receives and parses JSON."""
        client = WebSocketClient("wss://example.com/ws")
        mock_connection = AsyncMock()
        mock_connection.recv.return_value = '{"key": "value"}'
        client._connection = mock_connection

        result = await client.recv_json()

        assert result == {"key": "value"}


class TestWebSocketClientContextManager:
    """Test WebSocketClient async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_closes(self):
        """Context manager calls connect and close."""
        mock_connection = MagicMock()
        mock_connection.close = AsyncMock()

        async def mock_connect(*args, **kwargs):
            return mock_connection

        with patch("svc_infra.websocket.client.connect", side_effect=mock_connect):
            async with WebSocketClient("wss://example.com/ws") as client:
                assert client._connection is mock_connection

            # Should have closed
            assert client._closed is True

    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exception(self):
        """Context manager closes on exception."""
        mock_connection = MagicMock()
        mock_connection.close = AsyncMock()

        async def mock_connect(*args, **kwargs):
            return mock_connection

        with patch("svc_infra.websocket.client.connect", side_effect=mock_connect):
            try:
                async with WebSocketClient("wss://example.com/ws") as client:
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should still have closed
            assert client._closed is True


class TestWebSocketClientIterator:
    """Test WebSocketClient async iterator."""

    def test_has_aiter_method(self):
        """Client supports async iteration."""
        client = WebSocketClient("wss://example.com/ws")

        assert hasattr(client, "__aiter__")
        # The __aiter__ returns an async generator

    @pytest.mark.asyncio
    async def test_iterator_requires_connection(self):
        """Iterator raises when not connected."""
        client = WebSocketClient("wss://example.com/ws")

        # Should raise WebSocketError when not connected
        with pytest.raises(WebSocketError, match="Not connected"):
            async for msg in client:
                pass

    @pytest.mark.asyncio
    async def test_iterator_yields_messages(self):
        """Iterator yields received messages."""
        from websockets.exceptions import ConnectionClosedOK

        client = WebSocketClient("wss://example.com/ws")

        # Simulate receiving 2 messages then closing
        messages = ["msg1", "msg2"]
        call_count = [0]

        async def mock_iter():
            for msg in messages:
                yield msg

        # Need a mock connection that supports async iteration
        mock_connection = MagicMock()

        def aiter_impl(*args, **kwargs):
            return mock_iter().__aiter__()

        mock_connection.__aiter__ = aiter_impl
        client._connection = mock_connection

        received = []
        async for msg in client:
            received.append(msg)

        assert received == ["msg1", "msg2"]


class TestWebSocketClientConfig:
    """Test WebSocketClient configuration."""

    def test_uses_default_config(self):
        """Client uses default config when none provided."""
        client = WebSocketClient("wss://example.com/ws")

        assert client.config is not None
        # Check some defaults
        assert client.config.open_timeout == 10.0
        assert client.config.ping_interval == 20.0

    def test_custom_config_overrides_defaults(self):
        """Custom config overrides defaults."""
        config = WebSocketConfig(
            open_timeout=30.0,
            reconnect_enabled=False,
        )
        client = WebSocketClient("wss://example.com/ws", config=config)

        assert client.config.open_timeout == 30.0
        assert client.config.reconnect_enabled is False
