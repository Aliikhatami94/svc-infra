"""
WebSocket infrastructure for svc-infra.

Provides client and server-side WebSocket utilities:
- WebSocketClient: Connect to external WebSocket services
- ConnectionManager: Manage multiple server-side connections
- Easy builders for quick setup

Quick Start (Client):
    from svc_infra.websocket import easy_websocket_client

    async with easy_websocket_client("wss://api.example.com") as ws:
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
"""

from .client import WebSocketClient, websocket_connect
from .config import WebSocketConfig, get_default_config
from .exceptions import (
    AuthenticationError,
    ConnectionClosedError,
    ConnectionFailedError,
    MessageTooLargeError,
    WebSocketError,
)
from .models import ConnectionInfo, ConnectionState, WebSocketMessage

__all__ = [
    # Client
    "WebSocketClient",
    "websocket_connect",
    # Config
    "WebSocketConfig",
    "get_default_config",
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
]
