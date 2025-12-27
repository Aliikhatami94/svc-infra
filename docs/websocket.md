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

---

## Scaling with Redis Pub/Sub

For multi-instance deployments, WebSocket connections need coordination across instances. Redis pub/sub provides a scalable solution for message broadcasting.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Redis Pub/Sub                          │
│    (Channel: ws:broadcast, ws:room:{room_id}, ws:user:{id})    │
└─────────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │ App     │         │ App     │         │ App     │
    │ Instance│         │ Instance│         │ Instance│
    │    1    │         │    2    │         │    3    │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │  WS     │         │  WS     │         │  WS     │
    │ Clients │         │ Clients │         │ Clients │
    └─────────┘         └─────────┘         └─────────┘
```

### Redis-Backed ConnectionManager

```python
import asyncio
import json
from typing import Any
from redis.asyncio import Redis
from svc_infra.websocket import ConnectionManager

class RedisConnectionManager(ConnectionManager):
    """ConnectionManager with Redis pub/sub for multi-instance scaling.

    Each app instance:
    1. Maintains local WebSocket connections
    2. Subscribes to Redis channels for cross-instance messages
    3. Publishes broadcasts to Redis for other instances

    Args:
        redis_url: Redis connection URL
        channel_prefix: Prefix for Redis channels (default: "ws:")
        instance_id: Unique identifier for this instance (auto-generated if not provided)

    Example:
        >>> manager = RedisConnectionManager(
        ...     redis_url="redis://localhost:6379",
        ...     channel_prefix="myapp:ws:",
        ... )
        >>> await manager.start()  # Start listening to Redis
        >>> # ... use manager as normal
        >>> await manager.stop()   # Cleanup on shutdown
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        channel_prefix: str = "ws:",
        instance_id: str | None = None,
    ):
        super().__init__()
        self.redis_url = redis_url
        self.channel_prefix = channel_prefix
        self.instance_id = instance_id or self._generate_instance_id()

        self._redis: Redis | None = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._running = False

    def _generate_instance_id(self) -> str:
        """Generate unique instance identifier."""
        import uuid
        import socket
        return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

    async def start(self):
        """Start Redis connection and message listener."""
        self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()

        # Subscribe to broadcast channel
        await self._pubsub.psubscribe(f"{self.channel_prefix}*")

        # Start listener task
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_redis())

    async def stop(self):
        """Stop Redis connection and cleanup."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

    async def _listen_redis(self):
        """Listen for messages from Redis and deliver to local connections."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message and message["type"] == "pmessage":
                    await self._handle_redis_message(
                        message["channel"],
                        message["data"]
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue listening
                print(f"Redis listener error: {e}")
                await asyncio.sleep(1)

    async def _handle_redis_message(self, channel: str, data: str):
        """Handle incoming Redis message."""
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return

        # Skip messages from this instance (already delivered locally)
        if payload.get("_instance") == self.instance_id:
            return

        message = payload.get("message")
        if not message:
            return

        # Determine message type from channel
        channel_suffix = channel.removeprefix(self.channel_prefix)

        if channel_suffix == "broadcast":
            # Broadcast to all local connections
            exclude = payload.get("exclude_user")
            await super().broadcast(message, exclude_user=exclude)

        elif channel_suffix.startswith("room:"):
            # Room message
            room = channel_suffix.removeprefix("room:")
            exclude = payload.get("exclude_user")
            await super().broadcast_to_room(room, message, exclude_user=exclude)

        elif channel_suffix.startswith("user:"):
            # User-specific message
            user_id = channel_suffix.removeprefix("user:")
            await super().send_to_user(user_id, message)

    async def broadcast(
        self,
        message: dict[str, Any],
        *,
        exclude_user: str | None = None
    ):
        """Broadcast to all connected users across all instances."""
        # Publish to Redis for other instances
        await self._publish("broadcast", message, exclude_user=exclude_user)

        # Also deliver locally
        await super().broadcast(message, exclude_user=exclude_user)

    async def broadcast_to_room(
        self,
        room: str,
        message: dict[str, Any],
        *,
        exclude_user: str | None = None
    ):
        """Broadcast to room across all instances."""
        await self._publish(f"room:{room}", message, exclude_user=exclude_user)
        await super().broadcast_to_room(room, message, exclude_user=exclude_user)

    async def send_to_user(self, user_id: str, message: dict[str, Any]):
        """Send to user across all instances."""
        # Check if user is connected locally first
        if self.is_user_connected(user_id):
            await super().send_to_user(user_id, message)
        else:
            # User might be on another instance
            await self._publish(f"user:{user_id}", message)

    async def _publish(
        self,
        channel_suffix: str,
        message: dict[str, Any],
        **kwargs
    ):
        """Publish message to Redis channel."""
        if not self._redis:
            return

        payload = {
            "message": message,
            "_instance": self.instance_id,
            **kwargs
        }

        await self._redis.publish(
            f"{self.channel_prefix}{channel_suffix}",
            json.dumps(payload)
        )
```

### FastAPI Integration with Redis

```python
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager
import os

# Create Redis-backed manager
manager = RedisConnectionManager(
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    channel_prefix="myapp:ws:",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Redis
    await manager.start()
    yield
    # Shutdown: disconnect from Redis
    await manager.stop()

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()

            # Handle different message types
            match data.get("type"):
                case "broadcast":
                    await manager.broadcast({
                        "type": "message",
                        "from": user_id,
                        "data": data.get("data")
                    })

                case "room_message":
                    await manager.broadcast_to_room(
                        data.get("room"),
                        {"type": "message", "from": user_id, "data": data.get("data")}
                    )

                case "direct_message":
                    await manager.send_to_user(
                        data.get("to"),
                        {"type": "dm", "from": user_id, "data": data.get("data")}
                    )
    finally:
        await manager.disconnect(user_id, websocket)
```

### Room Membership with Redis

Track room membership across instances using Redis Sets:

```python
class RedisConnectionManager(ConnectionManager):
    """Extended with Redis-backed room membership."""

    async def join_room(self, user_id: str, room: str):
        """Join a room (tracked across all instances)."""
        # Track locally
        await super().join_room(user_id, room)

        # Track in Redis
        await self._redis.sadd(f"{self.channel_prefix}room_members:{room}", user_id)
        await self._redis.sadd(f"{self.channel_prefix}user_rooms:{user_id}", room)

        # Notify room members
        await self.broadcast_to_room(room, {
            "type": "user_joined",
            "user_id": user_id,
            "room": room
        })

    async def leave_room(self, user_id: str, room: str):
        """Leave a room."""
        await super().leave_room(user_id, room)

        await self._redis.srem(f"{self.channel_prefix}room_members:{room}", user_id)
        await self._redis.srem(f"{self.channel_prefix}user_rooms:{user_id}", room)

        await self.broadcast_to_room(room, {
            "type": "user_left",
            "user_id": user_id,
            "room": room
        })

    async def get_room_users_global(self, room: str) -> list[str]:
        """Get all users in room across all instances."""
        members = await self._redis.smembers(f"{self.channel_prefix}room_members:{room}")
        return list(members)

    async def get_user_rooms(self, user_id: str) -> list[str]:
        """Get all rooms a user is in across all instances."""
        rooms = await self._redis.smembers(f"{self.channel_prefix}user_rooms:{user_id}")
        return list(rooms)

    async def disconnect(self, user_id: str, websocket = None):
        """Disconnect and cleanup room memberships."""
        # Get user's rooms before disconnecting
        rooms = await self.get_user_rooms(user_id)

        # Leave all rooms
        for room in rooms:
            await self.leave_room(user_id, room)

        # Disconnect locally
        await super().disconnect(user_id, websocket)
```

### Presence Tracking

Track online users across all instances:

```python
class RedisConnectionManager(ConnectionManager):
    """Extended with presence tracking."""

    PRESENCE_TTL = 60  # seconds

    async def connect(self, user_id: str, websocket, metadata: dict = None):
        """Connect and mark user as online."""
        connection_id = await super().connect(user_id, websocket, metadata)

        # Mark user as online in Redis with TTL
        await self._redis.setex(
            f"{self.channel_prefix}presence:{user_id}",
            self.PRESENCE_TTL,
            json.dumps({
                "instance": self.instance_id,
                "connected_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            })
        )

        # Add to online users set
        await self._redis.sadd(f"{self.channel_prefix}online_users", user_id)

        # Start heartbeat task
        asyncio.create_task(self._heartbeat_presence(user_id))

        return connection_id

    async def _heartbeat_presence(self, user_id: str):
        """Refresh presence TTL while user is connected."""
        while self.is_user_connected(user_id):
            await self._redis.expire(
                f"{self.channel_prefix}presence:{user_id}",
                self.PRESENCE_TTL
            )
            await asyncio.sleep(self.PRESENCE_TTL // 2)

    async def disconnect(self, user_id: str, websocket = None):
        """Disconnect and update presence."""
        await super().disconnect(user_id, websocket)

        # Remove presence
        await self._redis.delete(f"{self.channel_prefix}presence:{user_id}")
        await self._redis.srem(f"{self.channel_prefix}online_users", user_id)

    async def get_online_users(self) -> list[str]:
        """Get all online users across all instances."""
        return list(await self._redis.smembers(f"{self.channel_prefix}online_users"))

    async def is_user_online(self, user_id: str) -> bool:
        """Check if user is online on any instance."""
        return await self._redis.exists(f"{self.channel_prefix}presence:{user_id}") > 0

    async def get_user_presence(self, user_id: str) -> dict | None:
        """Get user's presence info."""
        data = await self._redis.get(f"{self.channel_prefix}presence:{user_id}")
        return json.loads(data) if data else None
```

### Message Queue with Redis Streams

For reliable message delivery with persistence:

```python
class RedisStreamManager(RedisConnectionManager):
    """ConnectionManager using Redis Streams for message persistence."""

    STREAM_MAX_LEN = 10000  # Max messages per stream

    async def broadcast_persistent(
        self,
        message: dict[str, Any],
        *,
        stream_key: str = "broadcast"
    ):
        """Broadcast with message persistence."""
        # Add to Redis stream
        message_id = await self._redis.xadd(
            f"{self.channel_prefix}stream:{stream_key}",
            {"data": json.dumps(message)},
            maxlen=self.STREAM_MAX_LEN
        )

        # Also deliver via pub/sub for real-time
        await self.broadcast(message)

        return message_id

    async def get_message_history(
        self,
        stream_key: str = "broadcast",
        count: int = 100,
        since_id: str = "0"
    ) -> list[dict]:
        """Get message history from stream."""
        messages = await self._redis.xrange(
            f"{self.channel_prefix}stream:{stream_key}",
            min=since_id,
            count=count
        )

        return [
            {
                "id": msg_id,
                "data": json.loads(fields.get("data", "{}"))
            }
            for msg_id, fields in messages
        ]

    async def replay_messages_to_user(
        self,
        user_id: str,
        stream_key: str = "broadcast",
        since_id: str = "0"
    ):
        """Replay missed messages to a reconnecting user."""
        messages = await self.get_message_history(
            stream_key=stream_key,
            since_id=since_id
        )

        for msg in messages:
            await self.send_to_user(user_id, {
                "type": "replay",
                "message_id": msg["id"],
                "data": msg["data"]
            })
```

### Consumer Groups for Work Distribution

Distribute work across multiple consumers:

```python
class RedisConsumerManager:
    """Distribute WebSocket tasks across consumer instances."""

    def __init__(
        self,
        redis_url: str,
        stream_name: str = "ws:tasks",
        group_name: str = "ws:workers",
        consumer_name: str | None = None,
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
        self._redis: Redis | None = None

    async def start(self):
        """Initialize Redis and consumer group."""
        self._redis = Redis.from_url(self.redis_url, decode_responses=True)

        # Create consumer group (ignore if exists)
        try:
            await self._redis.xgroup_create(
                self.stream_name,
                self.group_name,
                mkstream=True
            )
        except Exception:
            pass  # Group already exists

    async def add_task(self, task: dict) -> str:
        """Add a task to the stream."""
        return await self._redis.xadd(
            self.stream_name,
            {"data": json.dumps(task)}
        )

    async def process_tasks(self, handler: callable):
        """Process tasks from the stream."""
        while True:
            # Read new messages
            messages = await self._redis.xreadgroup(
                self.group_name,
                self.consumer_name,
                {self.stream_name: ">"},
                count=10,
                block=5000  # 5 second timeout
            )

            if not messages:
                continue

            for stream, msg_list in messages:
                for msg_id, fields in msg_list:
                    try:
                        task = json.loads(fields.get("data", "{}"))
                        await handler(task)

                        # Acknowledge successful processing
                        await self._redis.xack(
                            self.stream_name,
                            self.group_name,
                            msg_id
                        )
                    except Exception as e:
                        # Log error, message will be redelivered
                        print(f"Task processing failed: {e}")

# Usage: distribute notification sending across instances
task_manager = RedisConsumerManager(
    redis_url="redis://localhost:6379",
    stream_name="notifications:tasks",
    group_name="notification:workers"
)

async def notification_handler(task: dict):
    """Handle notification task."""
    user_id = task.get("user_id")
    message = task.get("message")
    await manager.send_to_user(user_id, message)

# Start processing
await task_manager.start()
await task_manager.process_tasks(notification_handler)
```

---

## Load Balancing Configuration

### NGINX Configuration

```nginx
upstream websocket_backend {
    # Use IP hash for sticky sessions (recommended for WebSocket)
    ip_hash;

    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location /ws {
        proxy_pass http://websocket_backend;

        # WebSocket upgrade headers
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Headers for client IP preservation
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 3600s;  # 1 hour for long-lived connections
    }
}
```

### HAProxy Configuration

```haproxy
frontend http_front
    bind *:80
    acl is_websocket path_beg /ws
    use_backend websocket_back if is_websocket
    default_backend http_back

backend websocket_back
    balance source  # Sticky sessions based on source IP
    option http-server-close
    option forceclose

    server app1 app1:8000 check
    server app2 app2:8000 check
    server app3 app3:8000 check

    # WebSocket timeouts
    timeout tunnel 1h
    timeout client-fin 30s
```

### AWS Application Load Balancer

```yaml
# CloudFormation snippet
WebSocketTargetGroup:
  Type: AWS::ElasticLoadBalancingV2::TargetGroup
  Properties:
    HealthCheckPath: /health
    Port: 8000
    Protocol: HTTP
    TargetType: instance
    # Enable stickiness for WebSocket
    TargetGroupAttributes:
      - Key: stickiness.enabled
        Value: "true"
      - Key: stickiness.type
        Value: lb_cookie
      - Key: stickiness.lb_cookie.duration_seconds
        Value: "86400"  # 24 hours

WebSocketListenerRule:
  Type: AWS::ElasticLoadBalancingV2::ListenerRule
  Properties:
    Actions:
      - Type: forward
        TargetGroupArn: !Ref WebSocketTargetGroup
    Conditions:
      - Field: path-pattern
        Values:
          - /ws/*
    ListenerArn: !Ref HttpsListener
    Priority: 10
```

---

## Monitoring and Metrics

### Prometheus Metrics

```python
from prometheus_client import Counter, Gauge, Histogram
import time

# Define metrics
ws_connections_total = Counter(
    "websocket_connections_total",
    "Total WebSocket connections",
    ["instance"]
)

ws_connections_active = Gauge(
    "websocket_connections_active",
    "Currently active WebSocket connections",
    ["instance"]
)

ws_messages_sent = Counter(
    "websocket_messages_sent_total",
    "Total messages sent",
    ["instance", "type"]
)

ws_messages_received = Counter(
    "websocket_messages_received_total",
    "Total messages received",
    ["instance", "type"]
)

ws_message_duration = Histogram(
    "websocket_message_processing_seconds",
    "Message processing duration",
    ["instance", "type"]
)

class InstrumentedConnectionManager(RedisConnectionManager):
    """ConnectionManager with Prometheus metrics."""

    async def connect(self, user_id: str, websocket, metadata: dict = None):
        connection_id = await super().connect(user_id, websocket, metadata)

        ws_connections_total.labels(instance=self.instance_id).inc()
        ws_connections_active.labels(instance=self.instance_id).set(
            self.connection_count
        )

        return connection_id

    async def disconnect(self, user_id: str, websocket = None):
        await super().disconnect(user_id, websocket)

        ws_connections_active.labels(instance=self.instance_id).set(
            self.connection_count
        )

    async def broadcast(self, message: dict, **kwargs):
        start = time.time()
        await super().broadcast(message, **kwargs)

        ws_messages_sent.labels(
            instance=self.instance_id,
            type="broadcast"
        ).inc()
        ws_message_duration.labels(
            instance=self.instance_id,
            type="broadcast"
        ).observe(time.time() - start)
```

### Health Check Endpoint

```python
from fastapi import FastAPI, Request
from svc_infra.websocket import get_ws_manager

@app.get("/health/websocket")
async def websocket_health(request: Request):
    manager = get_ws_manager(request)

    # Check Redis connection
    redis_healthy = False
    if hasattr(manager, "_redis") and manager._redis:
        try:
            await manager._redis.ping()
            redis_healthy = True
        except Exception:
            pass

    # Get online users count (if using Redis presence)
    online_count = 0
    if hasattr(manager, "get_online_users"):
        online_count = len(await manager.get_online_users())

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "instance_id": getattr(manager, "instance_id", "local"),
        "local_connections": manager.connection_count,
        "local_users": len(manager.active_users),
        "local_rooms": manager.room_count,
        "global_online_users": online_count,
        "redis_connected": redis_healthy,
    }
```

---

## Real-World Examples

### Multi-Player Game Server

```python
from dataclasses import dataclass
from enum import Enum
import random

class GameState(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"

@dataclass
class Game:
    id: str
    players: list[str]
    state: GameState
    data: dict

class GameManager:
    """Real-time multiplayer game manager."""

    def __init__(self, ws_manager: RedisConnectionManager):
        self.ws = ws_manager
        self.games: dict[str, Game] = {}

    async def create_game(self, host_id: str) -> Game:
        """Create a new game room."""
        game_id = f"game_{random.randint(1000, 9999)}"
        game = Game(
            id=game_id,
            players=[host_id],
            state=GameState.WAITING,
            data={}
        )
        self.games[game_id] = game

        # Join WebSocket room
        await self.ws.join_room(host_id, game_id)

        return game

    async def join_game(self, game_id: str, player_id: str) -> Game:
        """Join an existing game."""
        game = self.games.get(game_id)
        if not game:
            raise ValueError("Game not found")

        if game.state != GameState.WAITING:
            raise ValueError("Game already in progress")

        game.players.append(player_id)
        await self.ws.join_room(player_id, game_id)

        # Notify all players
        await self.ws.broadcast_to_room(game_id, {
            "type": "player_joined",
            "player_id": player_id,
            "players": game.players,
        })

        return game

    async def start_game(self, game_id: str):
        """Start the game."""
        game = self.games[game_id]
        game.state = GameState.PLAYING

        await self.ws.broadcast_to_room(game_id, {
            "type": "game_started",
            "players": game.players,
        })

    async def handle_action(self, game_id: str, player_id: str, action: dict):
        """Handle a player action."""
        game = self.games[game_id]

        # Process action (game-specific logic)
        result = self._process_action(game, player_id, action)

        # Broadcast state update to all players
        await self.ws.broadcast_to_room(game_id, {
            "type": "state_update",
            "action": action,
            "result": result,
            "game_state": game.data,
        })
```

### Live Collaboration (Google Docs-style)

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Operation:
    """Operational transformation operation."""
    type: str  # insert, delete, retain
    position: int
    content: str | None = None
    length: int = 0
    user_id: str = ""
    timestamp: float = 0

class CollaborativeDocument:
    """Real-time collaborative document editing."""

    def __init__(self, doc_id: str, ws_manager: RedisConnectionManager):
        self.doc_id = doc_id
        self.ws = ws_manager
        self.content = ""
        self.operations: list[Operation] = []
        self.cursors: dict[str, int] = {}  # user_id -> cursor position

    async def apply_operation(self, op: Operation) -> bool:
        """Apply an operation and broadcast to collaborators."""
        # Apply operation to local state
        if op.type == "insert":
            self.content = (
                self.content[:op.position] +
                op.content +
                self.content[op.position:]
            )
        elif op.type == "delete":
            self.content = (
                self.content[:op.position] +
                self.content[op.position + op.length:]
            )

        self.operations.append(op)

        # Broadcast to all editors (except sender)
        await self.ws.broadcast_to_room(
            f"doc:{self.doc_id}",
            {
                "type": "operation",
                "operation": {
                    "type": op.type,
                    "position": op.position,
                    "content": op.content,
                    "length": op.length,
                    "user_id": op.user_id,
                    "timestamp": op.timestamp,
                }
            },
            exclude_user=op.user_id
        )

        return True

    async def update_cursor(self, user_id: str, position: int):
        """Update user's cursor position."""
        self.cursors[user_id] = position

        await self.ws.broadcast_to_room(
            f"doc:{self.doc_id}",
            {
                "type": "cursor",
                "user_id": user_id,
                "position": position,
            },
            exclude_user=user_id
        )

    async def join(self, user_id: str):
        """User joins the document session."""
        await self.ws.join_room(user_id, f"doc:{self.doc_id}")

        # Send current document state to new user
        await self.ws.send_to_user(user_id, {
            "type": "sync",
            "content": self.content,
            "cursors": self.cursors,
        })

        # Notify others
        await self.ws.broadcast_to_room(
            f"doc:{self.doc_id}",
            {"type": "user_joined", "user_id": user_id},
            exclude_user=user_id
        )
```

### Stock Ticker / Financial Data Stream

```python
import asyncio
from decimal import Decimal

class StockTicker:
    """Real-time stock price streaming."""

    def __init__(self, ws_manager: RedisConnectionManager):
        self.ws = ws_manager
        self.subscriptions: dict[str, set[str]] = {}  # symbol -> user_ids

    async def subscribe(self, user_id: str, symbols: list[str]):
        """Subscribe user to stock symbols."""
        for symbol in symbols:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = set()
            self.subscriptions[symbol].add(user_id)

            await self.ws.join_room(user_id, f"stock:{symbol}")

        # Send current prices
        for symbol in symbols:
            price = await self._get_current_price(symbol)
            await self.ws.send_to_user(user_id, {
                "type": "price",
                "symbol": symbol,
                "price": str(price),
            })

    async def unsubscribe(self, user_id: str, symbols: list[str]):
        """Unsubscribe user from stock symbols."""
        for symbol in symbols:
            if symbol in self.subscriptions:
                self.subscriptions[symbol].discard(user_id)
            await self.ws.leave_room(user_id, f"stock:{symbol}")

    async def publish_price_update(self, symbol: str, price: Decimal, change: Decimal):
        """Publish price update to all subscribers."""
        await self.ws.broadcast_to_room(f"stock:{symbol}", {
            "type": "price_update",
            "symbol": symbol,
            "price": str(price),
            "change": str(change),
            "change_percent": str((change / (price - change) * 100).quantize(Decimal("0.01"))),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current price (mock implementation)."""
        # In production, fetch from price service or database
        return Decimal("150.25")

# Usage
ticker = StockTicker(manager)

@app.websocket("/stocks")
async def stock_stream(websocket: WebSocket, user: WSIdentity):
    await manager.connect(user.id, websocket)

    try:
        async for data in websocket.iter_json():
            match data.get("action"):
                case "subscribe":
                    await ticker.subscribe(user.id, data.get("symbols", []))
                case "unsubscribe":
                    await ticker.unsubscribe(user.id, data.get("symbols", []))
    finally:
        await manager.disconnect(user.id, websocket)
```
