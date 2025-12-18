"""
Server-side WebSocket connection manager.

Provides:
- ConnectionManager: Track multiple connections per user
- Room/group support for targeted broadcasts
- Connection lifecycle hooks

Example:
    from svc_infra.websocket import ConnectionManager

    manager = ConnectionManager()

    @app.websocket("/ws/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, user_id: str):
        await manager.connect(user_id, websocket)
        try:
            async for message in websocket.iter_json():
                await manager.broadcast(message)
        finally:
            await manager.disconnect(user_id, websocket)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .models import ConnectionInfo

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Server-side WebSocket connection manager.

    Features:
    - Track multiple connections per user
    - Room/group support for targeted broadcasts
    - Connection lifecycle hooks
    - Thread-safe with asyncio.Lock

    Example:
        manager = ConnectionManager()

        @app.websocket("/ws/{user_id}")
        async def websocket_endpoint(websocket: WebSocket, user_id: str):
            await manager.connect(user_id, websocket)
            try:
                async for message in websocket.iter_json():
                    await manager.broadcast(message)
            finally:
                await manager.disconnect(user_id, websocket)
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # user_id -> list of (connection_id, WebSocket, ConnectionInfo)
        self._connections: dict[str, list[tuple[str, WebSocket, ConnectionInfo]]] = defaultdict(
            list
        )
        # room -> set of user_ids
        self._rooms: dict[str, set[str]] = defaultdict(set)
        # Lifecycle hooks
        self._on_connect: Callable[[str, WebSocket], Awaitable[None]] | None = None
        self._on_disconnect: Callable[[str, WebSocket], Awaitable[None]] | None = None

    async def connect(
        self,
        user_id: str,
        websocket: WebSocket,
        *,
        metadata: dict[str, Any] | None = None,
        accept: bool = True,
    ) -> str:
        """
        Register a new connection for a user.

        Args:
            user_id: Unique identifier for the user
            websocket: The WebSocket connection
            metadata: Optional metadata to store with the connection
            accept: Whether to call websocket.accept() (default: True)

        Returns:
            connection_id for tracking multiple connections per user
        """
        if accept:
            await websocket.accept()

        connection_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        info = ConnectionInfo(
            user_id=user_id,
            connection_id=connection_id,
            connected_at=now,
            last_activity=now,
            metadata=metadata or {},
        )

        async with self._lock:
            self._connections[user_id].append((connection_id, websocket, info))

        logger.debug(
            "User %s connected (connection_id=%s, total=%d)",
            user_id,
            connection_id,
            self.connection_count,
        )

        if self._on_connect:
            await self._on_connect(user_id, websocket)

        return connection_id

    async def disconnect(self, user_id: str, websocket: WebSocket | None = None) -> None:
        """
        Remove connection(s) for a user.

        Args:
            user_id: Unique identifier for the user
            websocket: If provided, only that connection is removed.
                      Otherwise, all connections for the user are removed.
        """
        removed_websocket = websocket

        async with self._lock:
            if websocket:
                # Remove specific connection
                self._connections[user_id] = [
                    (cid, ws, info)
                    for cid, ws, info in self._connections[user_id]
                    if ws is not websocket
                ]
            else:
                # Remove all connections for user
                if self._connections[user_id]:
                    # Get first websocket for disconnect callback
                    removed_websocket = self._connections[user_id][0][1]
                self._connections[user_id] = []

            # Clean up empty user entry
            if not self._connections[user_id]:
                del self._connections[user_id]
                # Remove from all rooms
                for room in list(self._rooms.keys()):
                    self._rooms[room].discard(user_id)
                    if not self._rooms[room]:
                        del self._rooms[room]

        logger.debug(
            "User %s disconnected (total=%d)",
            user_id,
            self.connection_count,
        )

        if self._on_disconnect and removed_websocket:
            await self._on_disconnect(user_id, removed_websocket)

    async def send_to_user(self, user_id: str, message: Any) -> int:
        """
        Send message to all connections for a user.

        Args:
            user_id: Target user ID
            message: Message to send (str, bytes, or JSON-serializable object)

        Returns:
            Number of connections message was sent to
        """
        sent = 0
        async with self._lock:
            connections = list(self._connections.get(user_id, []))

        for _, ws, info in connections:
            try:
                await self._send_message(ws, message)
                # Update last activity
                info.last_activity = datetime.now(UTC)
                sent += 1
            except Exception as e:
                logger.debug("Failed to send to user %s: %s", user_id, e)

        return sent

    async def broadcast(self, message: Any, *, exclude_user: str | None = None) -> int:
        """
        Broadcast message to all connected users.

        Args:
            message: Message to send (str, bytes, or JSON-serializable object)
            exclude_user: Optional user ID to exclude from broadcast

        Returns:
            Number of connections message was sent to
        """
        sent = 0
        async with self._lock:
            all_connections = [
                (uid, ws, info)
                for uid, conns in self._connections.items()
                for _, ws, info in conns
                if uid != exclude_user
            ]

        for uid, ws, info in all_connections:
            try:
                await self._send_message(ws, message)
                info.last_activity = datetime.now(UTC)
                sent += 1
            except Exception as e:
                logger.debug("Failed to broadcast to user %s: %s", uid, e)

        return sent

    async def _send_message(self, websocket: WebSocket, message: Any) -> None:
        """Send a message to a websocket, handling different message types."""
        if isinstance(message, str):
            await websocket.send_text(message)
        elif isinstance(message, bytes):
            await websocket.send_bytes(message)
        else:
            await websocket.send_json(message)

    # Room/group support

    async def join_room(self, user_id: str, room: str) -> None:
        """
        Add user to a room.

        Args:
            user_id: User to add
            room: Room name
        """
        async with self._lock:
            self._rooms[room].add(user_id)
        logger.debug("User %s joined room %s", user_id, room)

    async def leave_room(self, user_id: str, room: str) -> None:
        """
        Remove user from a room.

        Args:
            user_id: User to remove
            room: Room name
        """
        async with self._lock:
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.debug("User %s left room %s", user_id, room)

    async def broadcast_to_room(
        self, room: str, message: Any, *, exclude_user: str | None = None
    ) -> int:
        """
        Broadcast message to all users in a room.

        Args:
            room: Target room name
            message: Message to send
            exclude_user: Optional user ID to exclude

        Returns:
            Number of connections message was sent to
        """
        sent = 0
        async with self._lock:
            user_ids = set(self._rooms.get(room, set()))

        for user_id in user_ids:
            if user_id != exclude_user:
                sent += await self.send_to_user(user_id, message)

        return sent

    def get_room_users(self, room: str) -> list[str]:
        """Get list of user IDs in a room."""
        return list(self._rooms.get(room, set()))

    # Lifecycle hooks

    def on_connect(
        self, callback: Callable[[str, WebSocket], Awaitable[None]]
    ) -> Callable[[str, WebSocket], Awaitable[None]]:
        """
        Register callback for new connections.

        Can be used as a decorator:
            @manager.on_connect
            async def handle_connect(user_id: str, websocket: WebSocket):
                print(f"{user_id} connected")
        """
        self._on_connect = callback
        return callback

    def on_disconnect(
        self, callback: Callable[[str, WebSocket], Awaitable[None]]
    ) -> Callable[[str, WebSocket], Awaitable[None]]:
        """
        Register callback for disconnections.

        Can be used as a decorator:
            @manager.on_disconnect
            async def handle_disconnect(user_id: str, websocket: WebSocket):
                print(f"{user_id} disconnected")
        """
        self._on_disconnect = callback
        return callback

    # Introspection

    @property
    def active_users(self) -> list[str]:
        """List of connected user IDs."""
        return list(self._connections.keys())

    @property
    def connection_count(self) -> int:
        """Total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def room_count(self) -> int:
        """Number of active rooms."""
        return len(self._rooms)

    def get_user_connections(self, user_id: str) -> list[ConnectionInfo]:
        """Get connection info for a user."""
        return [info for _, _, info in self._connections.get(user_id, [])]

    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user has any active connections."""
        return user_id in self._connections and len(self._connections[user_id]) > 0
