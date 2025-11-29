"""
WebSocket infrastructure for svc-infra.

Provides client and server-side WebSocket utilities.

Quick Start (Client):
    from svc_infra.websocket import websocket_client

    async with websocket_client("wss://api.example.com") as ws:
        await ws.send_json({"hello": "world"})
        async for message in ws:
            print(message)

Quick Start (Server):
    from fastapi import FastAPI, WebSocket
    from svc_infra.websocket import add_websocket_manager

    app = FastAPI()
    manager = add_websocket_manager(app)

    @app.websocket("/ws/{user_id}")
    async def ws_endpoint(websocket: WebSocket, user_id: str):
        await manager.connect(user_id, websocket)
        try:
            async for msg in websocket.iter_json():
                await manager.broadcast(msg)
        finally:
            await manager.disconnect(user_id, websocket)

Quick Start (Auth):
    Use the dual router system for WebSocket authentication:

    from svc_infra.api.fastapi.dual import ws_protected_router
    from svc_infra.api.fastapi.auth.ws_security import WSIdentity

    router = ws_protected_router()

    @router.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, user: WSIdentity):
        await manager.connect(user.id, websocket)
        ...
"""

from .add import add_websocket_manager, get_ws_manager
from .client import WebSocketClient
from .config import WebSocketConfig
from .easy import easy_websocket_client, websocket_client
from .exceptions import (
    AuthenticationError,
    ConnectionClosedError,
    ConnectionFailedError,
    MessageTooLargeError,
    WebSocketError,
)
from .manager import ConnectionManager
from .models import ConnectionInfo, ConnectionState, WebSocketMessage

__all__ = [
    # Main API (simple)
    "websocket_client",
    "add_websocket_manager",
    "get_ws_manager",
    # Core classes (when you need more control)
    "WebSocketClient",
    "ConnectionManager",
    "WebSocketConfig",
    # Models
    "ConnectionState",
    "WebSocketMessage",
    "ConnectionInfo",
    # Exceptions
    "WebSocketError",
    "ConnectionClosedError",
    "ConnectionFailedError",
    "AuthenticationError",
    "MessageTooLargeError",
    # Backward compat
    "easy_websocket_client",
]
