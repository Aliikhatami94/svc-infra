"""Tests for ConnectionManager.

Tests connection lifecycle, messaging, rooms, and introspection.
"""

import pytest

pytestmark = pytest.mark.websocket
from unittest.mock import AsyncMock, MagicMock

from svc_infra.websocket.manager import ConnectionManager
from svc_infra.websocket.models import ConnectionInfo


class TestConnectionManagerInit:
    """Test ConnectionManager initialization."""

    def test_init_creates_empty_state(self):
        """Manager initializes with empty connection state."""
        manager = ConnectionManager()
        assert manager.connection_count == 0
        assert manager.active_users == []
        assert manager.room_count == 0

    def test_init_internal_state(self):
        """Manager has correct internal state."""
        manager = ConnectionManager()
        assert manager._connections == {}
        assert manager._rooms == {}
        assert manager._on_connect is None
        assert manager._on_disconnect is None


class TestConnectionManagerConnect:
    """Test ConnectionManager connect behavior."""

    @pytest.mark.asyncio
    async def test_connect_registers_user(self):
        """connect() registers user and websocket."""
        manager = ConnectionManager()
        ws = AsyncMock()

        connection_id = await manager.connect("user1", ws)

        assert manager.connection_count == 1
        assert "user1" in manager.active_users
        assert connection_id is not None

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        """connect() calls websocket.accept()."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)

        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_without_accept(self):
        """connect() can skip accept()."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws, accept=False)

        ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_multiple_users(self):
        """connect() handles multiple users."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)

        assert manager.connection_count == 2
        assert set(manager.active_users) == {"user1", "user2"}

    @pytest.mark.asyncio
    async def test_connect_same_user_multiple_times(self):
        """Same user can have multiple connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user1", ws2)

        assert manager.connection_count == 2
        connections = manager.get_user_connections("user1")
        assert len(connections) == 2

    @pytest.mark.asyncio
    async def test_connect_with_metadata(self):
        """connect() stores metadata."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws, metadata={"device": "mobile"})

        connections = manager.get_user_connections("user1")
        assert len(connections) == 1
        assert connections[0].metadata == {"device": "mobile"}

    @pytest.mark.asyncio
    async def test_connect_returns_unique_ids(self):
        """Each connection gets unique ID."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        id1 = await manager.connect("user1", ws1)
        id2 = await manager.connect("user1", ws2)

        assert id1 != id2


class TestConnectionManagerDisconnect:
    """Test ConnectionManager disconnect behavior."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        """disconnect() removes specific connection."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        await manager.disconnect("user1", ws)

        assert manager.connection_count == 0
        assert "user1" not in manager.active_users

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_connections(self):
        """disconnect() only removes specified connection."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user1", ws2)
        await manager.disconnect("user1", ws1)

        assert manager.connection_count == 1
        connections = manager.get_user_connections("user1")
        assert len(connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_all_for_user(self):
        """disconnect() without websocket removes all connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user1", ws2)
        await manager.disconnect("user1")

        assert manager.connection_count == 0
        assert "user1" not in manager.active_users


class TestConnectionManagerSendToUser:
    """Test ConnectionManager send_to_user behavior."""

    @pytest.mark.asyncio
    async def test_send_to_user_sends_json(self):
        """send_to_user() sends JSON message."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        sent = await manager.send_to_user("user1", {"msg": "hello"})

        assert sent == 1
        ws.send_json.assert_called_once_with({"msg": "hello"})

    @pytest.mark.asyncio
    async def test_send_to_user_sends_text(self):
        """send_to_user() sends text message."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        sent = await manager.send_to_user("user1", "hello")

        assert sent == 1
        ws.send_text.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_to_user_sends_bytes(self):
        """send_to_user() sends binary message."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        sent = await manager.send_to_user("user1", b"binary")

        assert sent == 1
        ws.send_bytes.assert_called_once_with(b"binary")

    @pytest.mark.asyncio
    async def test_send_to_user_sends_to_all_connections(self):
        """send_to_user() sends to all user connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user1", ws2)
        sent = await manager.send_to_user("user1", {"msg": "hello"})

        assert sent == 2
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_user_handles_unknown_user(self):
        """send_to_user() returns 0 for unknown user."""
        manager = ConnectionManager()

        sent = await manager.send_to_user("unknown", {"msg": "hello"})

        assert sent == 0


class TestConnectionManagerBroadcast:
    """Test ConnectionManager broadcast behavior."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        """broadcast() sends to all connected users."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)
        sent = await manager.broadcast({"msg": "hello"})

        assert sent == 2
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_exclude(self):
        """broadcast() can exclude specific user."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)
        sent = await manager.broadcast({"msg": "hello"}, exclude_user="user1")

        assert sent == 1
        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty(self):
        """broadcast() with no connections returns 0."""
        manager = ConnectionManager()

        sent = await manager.broadcast({"msg": "hello"})

        assert sent == 0


class TestConnectionManagerRooms:
    """Test ConnectionManager room/group support."""

    @pytest.mark.asyncio
    async def test_join_room(self):
        """join_room() adds user to room."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        await manager.join_room("user1", "general")

        members = manager.get_room_users("general")
        assert "user1" in members

    @pytest.mark.asyncio
    async def test_leave_room(self):
        """leave_room() removes user from room."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        await manager.join_room("user1", "general")
        await manager.leave_room("user1", "general")

        members = manager.get_room_users("general")
        assert "user1" not in members

    @pytest.mark.asyncio
    async def test_broadcast_to_room(self):
        """broadcast_to_room() sends to room members only."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)
        await manager.connect("user3", ws3)

        await manager.join_room("user1", "vip")
        await manager.join_room("user2", "vip")
        # user3 not in vip room

        sent = await manager.broadcast_to_room("vip", {"msg": "vip only"})

        assert sent == 2
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()
        ws3.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_room_with_exclude(self):
        """broadcast_to_room() can exclude user."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)
        await manager.join_room("user1", "vip")
        await manager.join_room("user2", "vip")

        sent = await manager.broadcast_to_room("vip", {"msg": "hello"}, exclude_user="user1")

        assert sent == 1
        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_rooms(self):
        """disconnect() removes user from all rooms."""
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect("user1", ws)
        await manager.join_room("user1", "room1")
        await manager.join_room("user1", "room2")
        await manager.disconnect("user1", ws)

        assert "user1" not in manager.get_room_users("room1")
        assert "user1" not in manager.get_room_users("room2")


class TestConnectionManagerQueries:
    """Test ConnectionManager introspection."""

    @pytest.mark.asyncio
    async def test_connection_count(self):
        """connection_count returns total connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        assert manager.connection_count == 0

        await manager.connect("user1", ws1)
        assert manager.connection_count == 1

        await manager.connect("user2", ws2)
        assert manager.connection_count == 2

    @pytest.mark.asyncio
    async def test_active_users(self):
        """active_users returns connected user IDs."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1)
        await manager.connect("user2", ws2)

        users = manager.active_users
        assert set(users) == {"user1", "user2"}

    @pytest.mark.asyncio
    async def test_get_user_connections(self):
        """get_user_connections returns ConnectionInfo list."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("user1", ws1, metadata={"device": "desktop"})
        await manager.connect("user1", ws2, metadata={"device": "mobile"})

        connections = manager.get_user_connections("user1")
        assert len(connections) == 2
        assert all(isinstance(c, ConnectionInfo) for c in connections)
        assert {c.metadata["device"] for c in connections} == {"desktop", "mobile"}

    @pytest.mark.asyncio
    async def test_is_user_connected(self):
        """is_user_connected checks connection status."""
        manager = ConnectionManager()
        ws = AsyncMock()

        assert manager.is_user_connected("user1") is False

        await manager.connect("user1", ws)
        assert manager.is_user_connected("user1") is True

        await manager.disconnect("user1", ws)
        assert manager.is_user_connected("user1") is False

    @pytest.mark.asyncio
    async def test_room_count(self):
        """room_count returns number of active rooms."""
        manager = ConnectionManager()
        ws = AsyncMock()

        assert manager.room_count == 0

        await manager.connect("user1", ws)
        await manager.join_room("user1", "room1")
        assert manager.room_count == 1

        await manager.join_room("user1", "room2")
        assert manager.room_count == 2


class TestConnectionManagerHooks:
    """Test ConnectionManager lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_on_connect_hook(self):
        """on_connect hook is called on connect."""
        manager = ConnectionManager()
        ws = AsyncMock()
        hook_called = []

        @manager.on_connect
        async def on_connect(user_id: str, websocket):
            hook_called.append((user_id, websocket))

        await manager.connect("user1", ws)

        assert len(hook_called) == 1
        assert hook_called[0] == ("user1", ws)

    @pytest.mark.asyncio
    async def test_on_disconnect_hook(self):
        """on_disconnect hook is called on disconnect."""
        manager = ConnectionManager()
        ws = AsyncMock()
        hook_called = []

        @manager.on_disconnect
        async def on_disconnect(user_id: str, websocket):
            hook_called.append((user_id, websocket))

        await manager.connect("user1", ws)
        await manager.disconnect("user1", ws)

        assert len(hook_called) == 1
        assert hook_called[0] == ("user1", ws)
