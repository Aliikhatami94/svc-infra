# Idempotency & Concurrency Control

svc-infra provides idempotency middleware and concurrency primitives to ensure safe
request handling in distributed systems. This prevents duplicate operations from
network retries, client bugs, or infrastructure failures.

---

## Why Idempotency Matters

Without idempotency protection:

```
Client → POST /payments → Server (success, 200)
       ← (network timeout, no response received)
Client → POST /payments → Server (duplicate charge!)
```

With idempotency:

```
Client → POST /payments + Idempotency-Key: abc123 → Server (success, 200)
       ← (network timeout, no response received)
Client → POST /payments + Idempotency-Key: abc123 → Server (cached 200, no duplicate)
```

---

## Quick Start

### Basic Middleware Setup

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.middleware import IdempotencyMiddleware

app = FastAPI()
app.add_middleware(IdempotencyMiddleware, ttl_seconds=86400)  # 24 hours
```

All POST, PATCH, and DELETE requests with an `Idempotency-Key` header will be cached.

### With Redis Store (Production)

```python
from redis import Redis
from svc_infra.api.fastapi.middleware import IdempotencyMiddleware, RedisIdempotencyStore

redis_client = Redis.from_url("redis://localhost:6379")
store = RedisIdempotencyStore(redis_client, prefix="myapp:idmp")

app.add_middleware(
    IdempotencyMiddleware,
    store=store,
    ttl_seconds=86400,
    skip_paths=["/v1/chat/stream", "/health"],
)
```

---

## How It Works

### Request Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        IdempotencyMiddleware                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Check method (POST/PATCH/DELETE only)                               │
│  2. Check skip_paths (streaming endpoints, health checks)               │
│  3. Extract Idempotency-Key header                                      │
│  4. Compute cache key: SHA256(method + path + idempotency_key)         │
│  5. Check store for existing entry:                                     │
│     ┌────────────────────────────────────────────────────────────┐     │
│     │ Entry exists and not expired?                               │     │
│     │   ├─ Payload hash matches? → Return cached response         │     │
│     │   └─ Payload hash differs? → Return 409 Conflict            │     │
│     │ Entry doesn't exist?                                        │     │
│     │   └─ Claim key, execute request, cache response             │     │
│     └────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cache Key Structure

The middleware creates a unique key from:

- HTTP method (POST, PATCH, DELETE)
- Request path
- Idempotency-Key header value

```python
def _cache_key(self, method: str, path: str, idkey: str) -> str:
    sig = hashlib.sha256((method + "|" + path + "|" + idkey).encode()).hexdigest()
    return f"idmp:{sig}"
```

### Payload Hash Validation

The middleware stores a hash of the request body. If a retry uses the same
idempotency key but different payload, a 409 Conflict is returned:

```json
{
  "type": "about:blank",
  "title": "Conflict",
  "detail": "Idempotency-Key re-used with different request payload."
}
```

---

## Configuration Options

### IdempotencyMiddleware Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ttl_seconds` | int | 86400 (24h) | How long to cache responses |
| `store` | IdempotencyStore | InMemoryStore | Storage backend |
| `header_name` | str | "Idempotency-Key" | Header to look for |
| `skip_paths` | list[str] | [] | Paths to skip (prefix matching) |

### Skip Paths

Use `skip_paths` for endpoints where caching is inappropriate:

```python
app.add_middleware(
    IdempotencyMiddleware,
    skip_paths=[
        "/v1/chat/stream",      # Streaming responses
        "/v1/chat/completions", # Large/streaming responses
        "/health",              # Health checks
        "/metrics",             # Metrics endpoint
    ],
)
```

**Important**: Skip paths use prefix matching. `/v1/chat` matches:
- `/v1/chat`
- `/v1/chat/stream`
- `/v1/chat/completions`

But NOT:
- `/api/v1/chat`
- `/v1/chatter`

---

## Storage Backends

### InMemoryIdempotencyStore

Default store, suitable for single-instance deployments or testing:

```python
from svc_infra.api.fastapi.middleware import InMemoryIdempotencyStore

store = InMemoryIdempotencyStore()
```

**Pros:**
- Zero external dependencies
- Fast (in-process)
- Good for development

**Cons:**
- Lost on restart
- No sharing across instances
- Memory grows with cached responses

### RedisIdempotencyStore

Production-ready store with distributed support:

```python
from redis import Redis
from svc_infra.api.fastapi.middleware import RedisIdempotencyStore

redis = Redis.from_url("redis://localhost:6379")
store = RedisIdempotencyStore(redis, prefix="myapp:idmp")
```

**Pros:**
- Survives restarts
- Shared across instances
- Automatic TTL expiration
- Scalable

**Cons:**
- External dependency (Redis)
- Network latency per request
- Requires Redis availability

### Storage Backend Comparison

| Feature | InMemory | Redis |
|---------|----------|-------|
| Persistence | ❌ | ✅ |
| Multi-instance | ❌ | ✅ |
| Setup complexity | None | Low |
| Latency | ~0ms | ~1-5ms |
| Memory usage | In-process | External |
| Production ready | ❌ | ✅ |

### Custom Store Implementation

Implement the `IdempotencyStore` protocol for custom backends:

```python
from dataclasses import dataclass
from svc_infra.api.fastapi.middleware import IdempotencyStore, IdempotencyEntry

@dataclass
class IdempotencyEntry:
    req_hash: str
    exp: float
    status: int | None = None
    body_b64: str | None = None
    headers: dict[str, str] | None = None
    media_type: str | None = None

class PostgresIdempotencyStore:
    def __init__(self, session_maker):
        self.session_maker = session_maker

    def get(self, key: str) -> IdempotencyEntry | None:
        # Query database for entry
        ...

    def set_initial(self, key: str, req_hash: str, exp: float) -> bool:
        # Atomically create entry if absent
        # Return True if created, False if already exists
        ...

    def set_response(
        self,
        key: str,
        *,
        status: int,
        body: bytes,
        headers: dict[str, str],
        media_type: str | None,
    ) -> None:
        # Update entry with response data
        ...

    def delete(self, key: str) -> None:
        # Remove entry
        ...
```

---

## Per-Route Enforcement

### Requiring Idempotency Keys

Force clients to provide idempotency keys for specific endpoints:

```python
from fastapi import Depends, Header, HTTPException

def require_idempotency_key(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for this endpoint.",
        )
    return idempotency_key

@app.post("/payments")
async def create_payment(
    request: PaymentRequest,
    idempotency_key: str = Depends(require_idempotency_key),
):
    # idempotency_key is guaranteed to be present
    ...
```

### Optional Idempotency

Some endpoints may work with or without idempotency keys:

```python
@app.post("/orders")
async def create_order(
    request: OrderRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if idempotency_key:
        # Client wants idempotency protection
        # Middleware will handle caching
        pass

    # Process order normally
    ...
```

---

## Idempotency Key Semantics

### Key Generation Strategies

**Client-generated UUIDs (Recommended):**

```python
import uuid

headers = {
    "Idempotency-Key": str(uuid.uuid4()),
}
response = requests.post("/payments", json=data, headers=headers)
```

**Request-derived keys:**

```python
# Based on request content
idempotency_key = hashlib.sha256(
    f"{user_id}:{order_id}:{amount}:{timestamp}".encode()
).hexdigest()
```

**External reference:**

```python
# Use external ID as idempotency key
idempotency_key = f"stripe_intent:{payment_intent_id}"
```

### Key Reuse Rules

1. **Same key + same payload** → Returns cached response ✅
2. **Same key + different payload** → Returns 409 Conflict ❌
3. **Different key + same payload** → Executes again (new operation) ⚠️

### TTL Considerations

Choose TTL based on your use case:

| Use Case | Recommended TTL |
|----------|-----------------|
| Payment processing | 24-48 hours |
| Order creation | 1-24 hours |
| General API calls | 1-4 hours |
| Short-lived operations | 5-15 minutes |

```python
# Short TTL for operations that should be retried quickly
app.add_middleware(IdempotencyMiddleware, ttl_seconds=900)  # 15 minutes

# Long TTL for financial operations
app.add_middleware(IdempotencyMiddleware, ttl_seconds=172800)  # 48 hours
```

---

## Optimistic Locking

For database-level concurrency control:

```python
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    status = Column(String)
    version = Column(Integer, default=1)  # Optimistic lock version

async def update_order_status(session, order_id: str, new_status: str, expected_version: int):
    order = await session.get(Order, order_id)

    if order.version != expected_version:
        raise HTTPException(409, "Order was modified by another request")

    order.status = new_status
    order.version += 1

    await session.commit()
    return order
```

### SQLAlchemy Version Column

```python
from sqlalchemy.orm import mapped_column

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {
        "version_id_col": version,
    }
```

SQLAlchemy will automatically check and increment the version on updates.

---

## Outbox Pattern

For reliable event publishing with exactly-once delivery:

```python
from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime, timezone

class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String, primary_key=True)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)

async def create_order_with_event(session, order_data: dict):
    # Create order and outbox event in same transaction
    order = Order(**order_data)
    session.add(order)

    event = OutboxEvent(
        id=str(uuid.uuid4()),
        aggregate_type="Order",
        aggregate_id=order.id,
        event_type="order.created",
        payload={"order_id": order.id, "amount": order.amount},
    )
    session.add(event)

    await session.commit()  # Both or neither
    return order
```

### Outbox Publisher Job

```python
@job_system.task(interval=5)  # Every 5 seconds
async def publish_outbox_events():
    async with async_session_maker() as session:
        # Get unpublished events
        events = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published == False)
            .order_by(OutboxEvent.created_at)
            .limit(100)
        )

        for event in events.scalars():
            try:
                await publish_to_kafka(event)
                event.published = True
                event.published_at = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Failed to publish event {event.id}: {e}")

        await session.commit()
```

---

## Inbox Pattern

For idempotent event consumption:

```python
class InboxEvent(Base):
    __tablename__ = "inbox_events"

    id = Column(String, primary_key=True)  # External event ID
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime, nullable=True)

async def handle_event(session, event_id: str, event_type: str, payload: dict):
    # Check if already processed
    existing = await session.get(InboxEvent, event_id)
    if existing:
        logger.info(f"Event {event_id} already processed, skipping")
        return

    # Record that we're processing this event
    inbox = InboxEvent(id=event_id, event_type=event_type)
    session.add(inbox)

    # Process the event
    await process_event(event_type, payload)

    inbox.processed_at = datetime.now(timezone.utc)
    await session.commit()
```

---

## Performance Considerations

### Redis Store Optimization

```python
# Use connection pooling
from redis import ConnectionPool, Redis

pool = ConnectionPool.from_url("redis://localhost:6379", max_connections=20)
redis = Redis(connection_pool=pool)
store = RedisIdempotencyStore(redis)
```

### Memory Management

For in-memory store, implement periodic cleanup:

```python
class CleanupInMemoryStore(InMemoryIdempotencyStore):
    def cleanup_expired(self):
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items()
            if v.exp <= now
        ]
        for k in expired_keys:
            del self._store[k]

# Run cleanup periodically
@job_system.task(interval=300)  # Every 5 minutes
async def cleanup_idempotency_store():
    store.cleanup_expired()
```

### Response Size Limits

Large responses consume more memory/storage. Consider:

```python
class SizeLimitedStore(RedisIdempotencyStore):
    MAX_BODY_SIZE = 1024 * 1024  # 1MB

    def set_response(self, key, *, status, body, headers, media_type):
        if len(body) > self.MAX_BODY_SIZE:
            # Don't cache large responses
            return
        super().set_response(key, status=status, body=body, headers=headers, media_type=media_type)
```

---

## Testing Idempotent Endpoints

### Basic Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_idempotent_create(client):
    idempotency_key = "test-key-123"

    # First request
    response1 = client.post(
        "/orders",
        json={"product": "widget", "quantity": 1},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201
    order_id = response1.json()["id"]

    # Retry with same key
    response2 = client.post(
        "/orders",
        json={"product": "widget", "quantity": 1},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 201
    assert response2.json()["id"] == order_id  # Same order returned

def test_idempotency_key_reuse_conflict(client):
    idempotency_key = "test-key-456"

    # First request
    response1 = client.post(
        "/orders",
        json={"product": "widget", "quantity": 1},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert response1.status_code == 201

    # Retry with same key but different payload
    response2 = client.post(
        "/orders",
        json={"product": "gadget", "quantity": 2},  # Different!
        headers={"Idempotency-Key": idempotency_key},
    )
    assert response2.status_code == 409
    assert "different request payload" in response2.json()["detail"]
```

### Concurrent Request Tests

```python
import asyncio
from httpx import AsyncClient

async def test_concurrent_idempotent_requests(async_client):
    idempotency_key = "concurrent-test"

    async def make_request():
        return await async_client.post(
            "/orders",
            json={"product": "widget"},
            headers={"Idempotency-Key": idempotency_key},
        )

    # Fire 10 concurrent requests with same key
    responses = await asyncio.gather(*[make_request() for _ in range(10)])

    # All should succeed
    assert all(r.status_code in (201, 200) for r in responses)

    # All should return same order ID
    order_ids = {r.json()["id"] for r in responses}
    assert len(order_ids) == 1  # Only one unique order
```

### Testing Store Expiration

```python
import time

def test_idempotency_key_expiration(client, short_ttl_store):
    """Test that expired keys allow new requests."""
    idempotency_key = "expiring-key"

    # First request
    response1 = client.post(
        "/orders",
        json={"product": "widget"},
        headers={"Idempotency-Key": idempotency_key},
    )
    order_id_1 = response1.json()["id"]

    # Wait for TTL to expire
    time.sleep(2)  # Assuming TTL is 1 second for test

    # New request with same key after expiration
    response2 = client.post(
        "/orders",
        json={"product": "widget"},
        headers={"Idempotency-Key": idempotency_key},
    )
    order_id_2 = response2.json()["id"]

    # Should be a new order
    assert order_id_1 != order_id_2
```

---

## Edge Cases and Gotchas

### Streaming Responses

Idempotency middleware buffers the response body. For streaming endpoints, skip them:

```python
app.add_middleware(
    IdempotencyMiddleware,
    skip_paths=["/v1/stream", "/v1/chat/completions"],
)
```

### File Uploads

For multipart form data, ensure the entire body is considered in the hash.
The default middleware hashes the raw body bytes, so this should work.

### Error Responses

Only successful responses (2xx) are cached by default. Failed requests can
be retried with the same idempotency key.

### Header Case Sensitivity

HTTP headers are case-insensitive. The middleware normalizes to lowercase:

```python
# All of these work:
"Idempotency-Key: abc123"
"idempotency-key: abc123"
"IDEMPOTENCY-KEY: abc123"
```

---

## See Also

- [API Integration](api.md) — FastAPI setup and middleware
- [Billing](billing.md) — Usage tracking with idempotency
- [Jobs](jobs.md) — Background job idempotency
- [Database](database.md) — Transaction isolation and locking
