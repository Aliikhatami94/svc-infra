# WebSocket Infrastructure

`svc_infra.websocket` provides production-ready WebSocket infrastructure for real-time communication. It includes both client-side capabilities (connecting to external WebSocket services) and server-side connection management (handling multiple client connections).

## Overview

The WebSocket module provides:

- **WebSocket Client**: Connect to external WebSocket services (OpenAI Realtime API, Gemini Live API, etc.)
- **Connection Manager**: Track and manage multiple server-side WebSocket connections
- **Authentication**: JWT-based authentication for WebSocket endpoints
- **Room/Group Support**: Target messages to specific groups of users
- **Auto-reconnection**: Built-in reconnection with exponential backoff
- **FastAPI Integration**: One-line setup with DualAPIRouter support
- **Environment Configuration**: `WS_*` environment variables for all settings

## Architecture

### Components

| Component | Purpose | Use Case |
|-----------|---------|----------|
| `WebSocketClient` | Connect to external WebSocket services | OpenAI Realtime API, third-party WebSockets |
| `ConnectionManager` | Track server-side connections | Real-time notifications, chat, live updates |
| `ws_protected_router` | Authenticated WebSocket routes | Secure WebSocket endpoints |
| `ws_public_router` | Public WebSocket routes | Echo servers, health checks |

### Client vs Server

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────┐              ┌─────────────────┐           │
│   │  WebSocketClient │              │ConnectionManager│           │
│   │  (Client-side)   │              │  (Server-side)  │           │
│   └────────┬────────┘              └────────┬────────┘           │
│            │                                 │                    │
│            ▼                                 ▼                    │
│   Connect to external              Handle incoming                │
│   WebSocket services               client connections             │
│   (OpenAI, Gemini, etc)           (browsers, mobile apps)        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Client: Connect to External WebSocket

```python
from svc_infra.websocket import easy_websocket_client

# Connect to external WebSocket service
async with easy_websocket_client("wss://api.example.com/ws") as ws:
    await ws.send_json({"type": "hello"})
    async for message in ws:
        print(f"Received: {message}")
```

### Server: Handle Client Connections

```python
from fastapi import FastAPI, WebSocket
from svc_infra.websocket import add_websocket_manager

app = FastAPI()
manager = add_websocket_manager(app)

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        async for message in websocket.iter_json():
            await manager.broadcast(message)
    finally:
        await manager.disconnect(user_id, websocket)
```

## WebSocket Client

The `WebSocketClient` class provides async WebSocket connections to external services.

### Basic Usage

```python
from svc_infra.websocket import WebSocketClient

async with WebSocketClient("wss://api.example.com/ws") as ws:
    # Send messages
    await ws.send("Hello, world!")           # Text
    await ws.send(b"binary data")            # Binary
    await ws.send_json({"type": "message"})  # JSON

    # Receive messages
    message = await ws.recv()                # Single message
    data = await ws.recv_json()              # Parse as JSON

    # Iterate over messages
    async for msg in ws:
        process(msg)
```

### With Custom Configuration

```python
from svc_infra.websocket import WebSocketClient, WebSocketConfig

config = WebSocketConfig(
    open_timeout=30.0,           # Connection timeout
    ping_interval=10.0,          # Keepalive ping interval
    ping_timeout=5.0,            # Pong response timeout
    max_message_size=16*1024*1024,  # 16MB for audio
    reconnect_enabled=True,
    reconnect_max_attempts=10,
)

async with WebSocketClient(
    "wss://api.openai.com/v1/realtime",
    config=config,
    headers={"Authorization": f"Bearer {api_key}"},
    subprotocols=["realtime"],
) as ws:
    await ws.send_json({"type": "session.update", ...})
```

### Auto-Reconnection

Use `websocket_connect` for automatic reconnection:

```python
from svc_infra.websocket import websocket_connect

async for ws in websocket_connect(url, auto_reconnect=True):
    try:
        async for message in ws:
            process(message)
    except ConnectionClosedError:
        continue  # Will automatically reconnect
```

### Client Properties

| Property | Type | Description |
|----------|------|-------------|
| `url` | `str` | WebSocket URL |
| `is_connected` | `bool` | Connection status |
| `latency` | `float` | RTT from ping/pong (seconds) |
| `config` | `WebSocketConfig` | Current configuration |

### Client Methods

| Method | Description |
|--------|-------------|
| `connect()` | Establish connection |
| `close(code, reason)` | Close connection gracefully |
| `send(data)` | Send text or binary message |
| `send_json(data)` | Send JSON message |
| `recv()` | Receive single message |
| `recv_json()` | Receive and parse JSON |

## Connection Manager

The `ConnectionManager` class tracks multiple server-side WebSocket connections.

### Basic Usage

```python
from svc_infra.websocket import ConnectionManager

manager = ConnectionManager()

# In your WebSocket endpoint
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    connection_id = await manager.connect(user_id, websocket)
    try:
        async for message in websocket.iter_json():
            # Send to specific user
            await manager.send_to_user(user_id, {"echo": message})

            # Broadcast to all
            await manager.broadcast({"from": user_id, "message": message})
    finally:
        await manager.disconnect(user_id, websocket)
```

### Room/Group Support

```python
# Join a room
await manager.join_room(user_id, "general")
await manager.join_room(user_id, "vip")

# Send to room members only
await manager.broadcast_to_room("general", {"msg": "Hello room!"})

# Leave room
await manager.leave_room(user_id, "general")
```

### Lifecycle Hooks

```python
manager = ConnectionManager()

@manager.on_connect
async def handle_connect(user_id: str, websocket: WebSocket):
    print(f"User {user_id} connected")
    await manager.broadcast({"event": "user_joined", "user": user_id})

@manager.on_disconnect
async def handle_disconnect(user_id: str, websocket: WebSocket):
    print(f"User {user_id} disconnected")
    await manager.broadcast({"event": "user_left", "user": user_id})
```

### Manager Properties

| Property | Type | Description |
|----------|------|-------------|
| `active_users` | `list[str]` | Connected user IDs |
| `connection_count` | `int` | Total connections |
| `room_count` | `int` | Active rooms |

### Manager Methods

| Method | Description |
|--------|-------------|
| `connect(user_id, ws, metadata)` | Register connection, returns connection_id |
| `disconnect(user_id, ws)` | Remove connection |
| `send_to_user(user_id, msg)` | Send to all user's connections |
| `broadcast(msg, exclude_user)` | Send to all connected users |
| `join_room(user_id, room)` | Add user to room |
| `leave_room(user_id, room)` | Remove user from room |
| `broadcast_to_room(room, msg)` | Send to room members |
| `get_user_connections(user_id)` | Get connection info list |
| `is_user_connected(user_id)` | Check if user is connected |
| `get_room_users(room)` | Get users in room |

## Authentication

WebSocket endpoints can require JWT authentication using `ws_protected_router` and related factories.

### Protected WebSocket Routes

```python
from svc_infra.api.fastapi.dual import ws_protected_router
from svc_infra.api.fastapi.dx import WSIdentity

router = ws_protected_router(prefix="/api")

@router.websocket("/ws")
async def secure_ws(websocket: WebSocket, user: WSIdentity):
    # user.id, user.email, user.scopes available from JWT
    await manager.connect(user.id, websocket)
    ...
```

### Router Factories

| Factory | Description |
|---------|-------------|
| `ws_public_router()` | No authentication required |
| `ws_protected_router()` | Requires valid JWT |
| `ws_user_router()` | JWT only (no API keys) |
| `ws_scopes_router(*scopes)` | Requires specific scopes |
| `ws_optional_router()` | Auth optional (anonymous allowed) |

### Token Passing

Clients can pass JWT tokens via:

1. **Query Parameter** (recommended for browsers):
   ```javascript
   new WebSocket("wss://api.example.com/ws?token=eyJ...")
   ```

2. **Authorization Header** (for non-browser clients):
   ```python
   headers = {"Authorization": "Bearer eyJ..."}
   ```

3. **Subprotocol** (for browser clients needing headers):
   ```javascript
   new WebSocket("wss://api.example.com/ws", ["bearer", "eyJ..."])
   ```

### Auth Types

| Type | Description |
|------|-------------|
| `WSPrincipal` | Lightweight principal with JWT claims only |
| `WSIdentity` | Annotated type for required auth |
| `OptionalWSIdentity` | Auth optional, may be None |
| `RequireWSScopes` | Guard for specific scopes |
| `RequireWSAnyScope` | Guard for any of specified scopes |

## FastAPI Integration

### One-Line Setup

```python
from fastapi import FastAPI
from svc_infra.websocket import add_websocket_manager

app = FastAPI()
manager = add_websocket_manager(app)
```

### Get Manager in Routes

```python
from svc_infra.websocket import get_ws_manager

@app.get("/ws/stats")
async def ws_stats(request: Request):
    manager = get_ws_manager(request)
    return {
        "connections": manager.connection_count,
        "users": manager.active_users,
        "rooms": manager.room_count,
    }
```

### With DualAPIRouter

```python
from svc_infra.api.fastapi.dual import ws_public_router

router = ws_public_router(prefix="/realtime")

@router.websocket("/events")
async def events_ws(websocket: WebSocket):
    await websocket.accept()
    ...
```

## Configuration

### Environment Variables

All settings can be configured via `WS_*` environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WS_OPEN_TIMEOUT` | `10.0` | Connection timeout (seconds) |
| `WS_CLOSE_TIMEOUT` | `10.0` | Close handshake timeout |
| `WS_PING_INTERVAL` | `20.0` | Keepalive ping interval (None to disable) |
| `WS_PING_TIMEOUT` | `20.0` | Pong response timeout |
| `WS_MAX_MESSAGE_SIZE` | `1048576` | Max message size (1MB) |
| `WS_MAX_QUEUE_SIZE` | `16` | Max queued messages |
| `WS_RECONNECT_ENABLED` | `true` | Enable auto-reconnection |
| `WS_RECONNECT_MAX_ATTEMPTS` | `5` | Max reconnect attempts (0=infinite) |
| `WS_RECONNECT_BACKOFF_BASE` | `1.0` | Base backoff (seconds) |
| `WS_RECONNECT_BACKOFF_MAX` | `60.0` | Max backoff (seconds) |
| `WS_RECONNECT_JITTER` | `0.1` | Jitter factor (0-1) |

### Programmatic Configuration

```python
from svc_infra.websocket import WebSocketConfig

config = WebSocketConfig(
    open_timeout=30.0,
    ping_interval=10.0,
    max_message_size=16 * 1024 * 1024,  # 16MB
    reconnect_enabled=True,
    reconnect_max_attempts=10,
)
```

## Examples

### Real-Time Notifications

```python
from fastapi import FastAPI, WebSocket, Depends
from svc_infra.websocket import add_websocket_manager
from svc_infra.api.fastapi.dx import WSIdentity

app = FastAPI()
manager = add_websocket_manager(app)

@app.websocket("/notifications")
async def notifications(websocket: WebSocket, user: WSIdentity):
    await manager.connect(user.id, websocket)
    try:
        # Keep connection open for push notifications
        while True:
            # Wait for messages from client (heartbeat, etc)
            await websocket.receive_text()
    finally:
        await manager.disconnect(user.id, websocket)

# From your business logic, push notifications:
async def notify_user(user_id: str, notification: dict):
    await manager.send_to_user(user_id, {
        "type": "notification",
        "data": notification,
    })
```

### Chat Application

```python
@app.websocket("/chat/{room}")
async def chat_room(websocket: WebSocket, room: str, user: WSIdentity):
    await manager.connect(user.id, websocket)
    await manager.join_room(user.id, room)

    try:
        # Announce join
        await manager.broadcast_to_room(room, {
            "type": "system",
            "message": f"{user.id} joined the room",
        })

        async for data in websocket.iter_json():
            # Broadcast message to room
            await manager.broadcast_to_room(room, {
                "type": "message",
                "from": user.id,
                "message": data.get("message"),
            }, exclude_user=user.id)  # Don't echo back to sender
    finally:
        await manager.leave_room(user.id, room)
        await manager.disconnect(user.id, websocket)
        await manager.broadcast_to_room(room, {
            "type": "system",
            "message": f"{user.id} left the room",
        })
```

### Live Dashboard Updates

```python
import asyncio

# Background task to push updates
async def push_dashboard_updates():
    while True:
        stats = await get_dashboard_stats()
        await manager.broadcast({
            "type": "dashboard_update",
            "data": stats,
        })
        await asyncio.sleep(5)  # Update every 5 seconds

@app.on_event("startup")
async def start_dashboard_updates():
    asyncio.create_task(push_dashboard_updates())

@app.websocket("/dashboard/live")
async def dashboard_ws(websocket: WebSocket, user: WSIdentity):
    await manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    finally:
        await manager.disconnect(user.id, websocket)
```

### OpenAI Realtime API Integration

```python
from svc_infra.websocket import WebSocketClient, WebSocketConfig

async def openai_realtime_session(api_key: str):
    config = WebSocketConfig(
        ping_interval=30.0,
        max_message_size=16 * 1024 * 1024,  # 16MB for audio
    )

    async with WebSocketClient(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
        config=config,
        headers={
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as ws:
        # Configure session
        await ws.send_json({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": "alloy",
            },
        })

        # Handle events
        async for event in ws:
            event_data = json.loads(event)
            match event_data.get("type"):
                case "session.created":
                    print("Session started")
                case "response.audio.delta":
                    audio_chunk = base64.b64decode(event_data["delta"])
                    play_audio(audio_chunk)
                case "error":
                    print(f"Error: {event_data}")
```

## Production Recommendations

### Scaling

For multi-instance deployments, use Redis pub/sub to synchronize messages across instances:

```python
# Future: Redis-backed ConnectionManager
manager = ConnectionManager(
    redis_url="redis://localhost:6379",
    channel_prefix="ws:",
)
```

> **Note**: Redis pub/sub support is planned for a future release. For now, use sticky sessions or a single instance.

### Load Balancing

Configure your load balancer for WebSocket support:

- **NGINX**: Use `proxy_http_version 1.1` and `Upgrade` headers
- **AWS ALB**: Enable WebSocket support in target group
- **Cloudflare**: WebSockets supported on all plans

### Health Checks

```python
@app.get("/health/websocket")
async def websocket_health(request: Request):
    manager = get_ws_manager(request)
    return {
        "status": "healthy",
        "connections": manager.connection_count,
        "users": len(manager.active_users),
    }
```

### Connection Limits

Set appropriate limits to prevent resource exhaustion:

```python
manager = ConnectionManager()
MAX_CONNECTIONS_PER_USER = 5

@app.websocket("/ws")
async def limited_ws(websocket: WebSocket, user: WSIdentity):
    if len(manager.get_user_connections(user.id)) >= MAX_CONNECTIONS_PER_USER:
        await websocket.close(code=4008, reason="Too many connections")
        return

    await manager.connect(user.id, websocket)
    ...
```

### Graceful Shutdown

```python
@app.on_event("shutdown")
async def shutdown_websockets():
    # Notify all clients
    await manager.broadcast({
        "type": "system",
        "message": "Server shutting down",
    })

    # Close all connections
    for user_id in manager.active_users:
        await manager.disconnect(user_id)
```

## Exceptions

| Exception | Description |
|-----------|-------------|
| `WebSocketError` | Base exception for all WebSocket errors |
| `ConnectionClosedError` | Connection was closed (includes code and reason) |
| `ConnectionFailedError` | Failed to establish connection |
| `AuthenticationError` | WebSocket authentication failed |
| `MessageTooLargeError` | Message exceeds `max_message_size` |

## API Reference

### Module Exports

```python
from svc_infra.websocket import (
    # Client
    WebSocketClient,
    websocket_connect,
    easy_websocket_client,

    # Server
    ConnectionManager,
    easy_websocket_manager,
    add_websocket_manager,
    get_ws_manager,

    # Config
    WebSocketConfig,
    get_default_config,

    # Models
    ConnectionState,
    WebSocketMessage,
    ConnectionInfo,

    # Exceptions
    WebSocketError,
    ConnectionClosedError,
    ConnectionFailedError,
    AuthenticationError,
    MessageTooLargeError,
)
```

### Auth Exports (from dx.py)

```python
from svc_infra.api.fastapi.dx import (
    # Types
    WSPrincipal,
    WSIdentity,
    OptionalWSIdentity,

    # Guards
    RequireWSIdentity,
    AllowWSIdentity,
    RequireWSScopes,
    RequireWSAnyScope,

    # Routers
    ws_public_router,
    ws_protected_router,
    ws_user_router,
    ws_scopes_router,
    ws_optional_router,
)
```

## See Also

- [Authentication](auth.md) - HTTP authentication patterns
- [API Documentation](api.md) - FastAPI integration patterns
- [Storage](storage.md) - File storage infrastructure
