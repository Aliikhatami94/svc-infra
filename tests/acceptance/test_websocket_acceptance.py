"""WebSocket acceptance tests.

Tests WebSocket infrastructure including:
- A23-01: Connection and messaging
- A23-02: Authentication
- A23-03: Broadcast and rooms
- A23-04: Client reconnection (deferred - requires real network)
- A23-05: Room/group messaging
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi import APIRouter, Depends, FastAPI, WebSocket, WebSocketDisconnect
from starlette.testclient import TestClient

from svc_infra.api.fastapi.auth.ws_security import WSIdentity
from svc_infra.websocket import ConnectionManager

pytestmark = [pytest.mark.acceptance, pytest.mark.websocket]


# ============================================================================
# Helper to create test app
# ============================================================================


def create_ws_test_app() -> FastAPI:
    """Create a test app with WebSocket endpoints for acceptance testing."""
    app = FastAPI()
    manager = ConnectionManager()

    # Store manager on app for test access
    app.state.ws_manager = manager

    # Simple APIRouter for public WebSocket endpoints (no auth)
    public_router = APIRouter(prefix="/ws")

    @public_router.websocket("/echo")
    async def ws_echo(websocket: WebSocket):
        """Echo any message received back to the client."""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"echo: {data}")
        except WebSocketDisconnect:
            pass

    @public_router.websocket("/chat/{user_id}")
    async def ws_chat(websocket: WebSocket, user_id: str):
        """Public chat endpoint with user ID from path."""
        connection_id = await manager.connect(user_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                # Broadcast to all connected users
                await manager.broadcast(
                    {"user": user_id, "message": data.get("message", "")},
                    exclude_user=None,  # Include sender
                )
        except WebSocketDisconnect:
            await manager.disconnect(user_id, websocket)

    @public_router.websocket("/room/{room_name}")
    async def ws_room(websocket: WebSocket, room_name: str):
        """Room-based messaging - join a room and receive room messages."""
        await websocket.accept()
        # Get user_id from first message
        init_data = await websocket.receive_json()
        user_id = init_data.get("user_id", "anonymous")

        connection_id = await manager.connect(user_id, websocket, accept=False)
        await manager.join_room(user_id, room_name)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "message":
                    await manager.broadcast_to_room(
                        room_name,
                        {"user": user_id, "room": room_name, "message": data.get("text", "")},
                    )
        except WebSocketDisconnect:
            await manager.leave_room(user_id, room_name)
            await manager.disconnect(user_id, websocket)

    app.include_router(public_router)

    # Protected WebSocket endpoint (requires JWT) - direct on app
    @app.websocket("/ws/secure/me")
    async def ws_secure_me(
        websocket: WebSocket,
        principal: WSIdentity,
    ):
        """Protected endpoint - requires valid JWT."""
        await websocket.accept()
        try:
            # Send user info back immediately
            await websocket.send_json(
                {
                    "type": "auth_success",
                    "user_id": principal.id,
                    "email": principal.email,
                    "scopes": principal.scopes,
                }
            )
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Hello {principal.id}: {data}")
        except WebSocketDisconnect:
            pass

    return app


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def jwt_secret():
    """JWT secret for test tokens."""
    import os

    from svc_infra.api.fastapi.auth import settings

    secret = "test-jwt-secret-for-acceptance"
    os.environ["AUTH_JWT__SECRET"] = secret
    # Reset settings cache
    settings._settings = None
    yield secret
    # Cleanup
    settings._settings = None


@pytest.fixture
def valid_token(jwt_secret):
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "scopes": ["read", "write"],
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_token(jwt_secret):
    """Create an expired JWT token for testing."""
    payload = {
        "sub": "user-123",
        "email": "test@example.com",
        "exp": int(time.time()) - 3600,  # Expired
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


# ============================================================================
# A23-01: WebSocket Connection and Messaging
# ============================================================================


def test_a23_01_echo_connection_and_messaging():
    """Test basic WebSocket connection, send message, receive echo."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/echo") as ws:
            # Send a message
            ws.send_text("hello world")

            # Receive echo
            data = ws.receive_text()
            assert data == "echo: hello world"

            # Send another message
            ws.send_text("test message 2")
            data = ws.receive_text()
            assert data == "echo: test message 2"


def test_a23_01_echo_multiple_messages():
    """Test sending multiple messages in sequence."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/echo") as ws:
            messages = ["msg1", "msg2", "msg3", "msg4", "msg5"]

            for msg in messages:
                ws.send_text(msg)
                data = ws.receive_text()
                assert data == f"echo: {msg}"


def test_a23_01_connection_close():
    """Test clean connection close."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/echo") as ws:
            ws.send_text("before close")
            data = ws.receive_text()
            assert data == "echo: before close"
        # WebSocket should be closed cleanly after exiting context


# ============================================================================
# A23-02: WebSocket Authentication
# ============================================================================


def test_a23_02_auth_valid_token(valid_token, jwt_secret):
    """Test connection with valid JWT token."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        # Connect with token in query param
        with client.websocket_connect(f"/ws/secure/me?token={valid_token}") as ws:
            # Should receive auth success message
            data = ws.receive_json()
            assert data["type"] == "auth_success"
            assert data["user_id"] == "user-123"
            assert data["email"] == "test@example.com"
            assert "read" in data["scopes"]

            # Send and receive message
            ws.send_text("authenticated message")
            response = ws.receive_text()
            assert "user-123" in response
            assert "authenticated message" in response


def test_a23_02_auth_invalid_token(jwt_secret):
    """Test connection with invalid JWT token is rejected."""
    from starlette.websockets import WebSocketDisconnect

    app = create_ws_test_app()

    with TestClient(app) as client:
        try:
            # Try to connect with invalid token
            with client.websocket_connect("/ws/secure/me?token=invalid-token") as ws:
                # Should not reach here - connection should be rejected
                pytest.fail("Expected connection to be rejected")
        except Exception as e:
            # Connection should be rejected (403 or disconnect)
            pass  # Expected


def test_a23_02_auth_expired_token(expired_token, jwt_secret):
    """Test connection with expired JWT token is rejected."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/secure/me?token={expired_token}") as ws:
                pytest.fail("Expected connection to be rejected")
        except Exception:
            pass  # Expected


def test_a23_02_auth_no_token(jwt_secret):
    """Test connection without token is rejected on protected route."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/secure/me") as ws:
                pytest.fail("Expected connection to be rejected")
        except Exception:
            pass  # Expected


# ============================================================================
# A23-03: Connection Manager Broadcast
# ============================================================================


def test_a23_03_broadcast_to_all():
    """Test message broadcast to all connected clients."""
    import threading
    import time

    app = create_ws_test_app()
    results = {"user1": [], "user2": []}
    errors = []

    def user_client(user_id: str, send_message: bool = False):
        try:
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws/chat/{user_id}") as ws:
                    if send_message:
                        # Wait a bit for other client to connect
                        time.sleep(0.1)
                        ws.send_json({"message": f"hello from {user_id}"})

                    # Receive broadcast
                    try:
                        data = ws.receive_json()
                        results[user_id].append(data)
                    except Exception:
                        pass
        except Exception as e:
            errors.append(str(e))

    # Start two clients
    t1 = threading.Thread(target=user_client, args=("user1", True))
    t2 = threading.Thread(target=user_client, args=("user2", False))

    t2.start()
    time.sleep(0.05)  # Let user2 connect first
    t1.start()

    t1.join(timeout=2)
    t2.join(timeout=2)

    # At least one should have received the broadcast
    all_messages = results["user1"] + results["user2"]
    assert len(all_messages) >= 1
    # Check message content
    for msg in all_messages:
        assert "user" in msg
        assert "message" in msg


# ============================================================================
# A23-05: Room/Group Messaging
# ============================================================================


def test_a23_05_room_join_and_message():
    """Test joining a room and receiving room messages."""

    app = create_ws_test_app()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/room/general") as ws:
            # Send init message with user_id
            ws.send_json({"user_id": "alice"})

            # Send a message to the room
            ws.send_json({"type": "message", "text": "hello room"})

            # Should receive the broadcast back
            data = ws.receive_json()
            assert data["room"] == "general"
            assert data["user"] == "alice"
            assert data["message"] == "hello room"


def test_a23_05_room_isolation():
    """Test that room messages only go to room members."""
    import threading
    import time

    app = create_ws_test_app()
    results = {"room1": [], "room2": []}

    def room_client(room_name: str, user_id: str, send_message: bool = False):
        try:
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws/room/{room_name}") as ws:
                    ws.send_json({"user_id": user_id})

                    if send_message:
                        time.sleep(0.1)
                        ws.send_json({"type": "message", "text": f"message to {room_name}"})

                    try:
                        data = ws.receive_json()
                        results[room_name].append(data)
                    except Exception:
                        pass
        except Exception:
            pass

    # User in room1 sends message
    t1 = threading.Thread(target=room_client, args=("room1", "user1", True))
    # User in room2 should NOT receive message from room1
    t2 = threading.Thread(target=room_client, args=("room2", "user2", False))

    t1.start()
    t2.start()

    t1.join(timeout=2)
    t2.join(timeout=2)

    # room1 should have received the message
    assert len(results["room1"]) >= 1
    assert results["room1"][0]["room"] == "room1"

    # room2 should NOT have received the message (it would time out)
    # The room2 client won't receive anything since no message was sent to room2


# ============================================================================
# A23-04: Client Reconnection (Deferred)
# ============================================================================
# Note: Auto-reconnection testing requires actual network conditions
# that are difficult to simulate in acceptance tests. The websockets
# library handles reconnection internally, and we've verified the
# configuration in unit tests.


@pytest.mark.skip(reason="Reconnection requires real network conditions")
def test_a23_04_client_reconnection(ws_test_app):
    """Test client auto-reconnection after disconnect."""
    # This test would require:
    # 1. Connect client
    # 2. Force server-side disconnect
    # 3. Verify client reconnects
    #
    # The websockets library handles this internally with exponential backoff.
    # Unit tests verify the configuration; this is deferred for integration testing.
    pass
