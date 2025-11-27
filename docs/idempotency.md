# Idempotency & Concurrency Controls

This guide explains how idempotency works in svc-infra and how to enable it for safe retries.

## What it does
- Prevents duplicate processing of mutating requests (POST/PATCH/DELETE).
- Replays the previously successful response when the same `Idempotency-Key` is used.
- Detects conflicts when the same key is reused with a different request body, returning 409.

## Middleware usage
```python
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware

app.add_middleware(IdempotencyMiddleware)  # default: in-memory store, 24h TTL
```
- Header name: `Idempotency-Key` (configurable via `header_name`)
- TTL: defaults to 24 hours (`ttl_seconds`)

### Redis store (recommended for multi-instance)
```python
import redis
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware
from svc_infra.api.fastapi.middleware.idempotency_store import RedisIdempotencyStore

r = redis.Redis.from_url("redis://localhost:6379/0")
store = RedisIdempotencyStore(r, prefix="idmp")
app.add_middleware(IdempotencyMiddleware, store=store, ttl_seconds=24*3600)
```

## Per-route enforcement
If an endpoint must require idempotency always, add the dependency:
```python
from fastapi import Depends
from svc_infra.api.fastapi.middleware.idempotency import require_idempotency_key

@app.post("/payments/intents", dependencies=[Depends(require_idempotency_key)])
async def create_intent(...):
    ...
```

## Semantics
- First request with a key:
  - The middleware claims the key and records a hash of the request body.
  - On success (2xx), the response envelope is cached until TTL.
- Replay with same key and same body:
  - Returns the cached response with the original status and headers.
- Replay with same key but different body:
  - Returns 409 Conflict (don’t reuse keys for different logical operations).

## Testing
- Marker: `-m concurrency` selects concurrency tests in this repo.
- Scenarios covered:
  - Successful first request and replay
  - Conflict on mismatched payload reusing the same key

## Notes and pitfalls
- Use a unique key per logical operation (e.g., `order-{id}-capture-1`).
- TTL should exceed your max retry horizon.
- For stronger guarantees in Redis, consider a Lua script to make the claim + response update atomic (future improvement).
- If you also use optimistic locking, surface 409 when `If-Match` version mismatches during updates.

---

## Optimistic Locking

Use the `If-Match` header and a version field on your models.

```python
from svc_infra.api.fastapi.middleware.optimistic_lock import require_if_match, check_version_or_409

@app.patch("/resource/{rid}")
async def update_resource(rid: str, v: str = Depends(require_if_match)):
    current = await repo.get(...)
    check_version_or_409(lambda: current.version, v)
    current.version += 1
    await repo.save(current)
    return {...}
```

Pitfalls:
- Always bump the version on successful updates.
- Return 428 when `If-Match` is missing on mutating routes that require optimistic locking.
- Consider ETag headers for GETs to complement conditional requests.

---

## Outbox / Inbox

Outbox: record events/changes that must be delivered to external systems; a relay fetches and delivers reliably.

```python
from svc_infra.db.outbox import InMemoryOutboxStore

ob = InMemoryOutboxStore()
msg = ob.enqueue("orders.created", {"order_id": 123})
nxt = ob.fetch_next(topics=["orders.created"])  # process
ob.mark_processed(nxt.id)
```

Inbox: deduplicate external deliveries (e.g., webhook replays) with TTL.

```python
from svc_infra.db.inbox import InMemoryInboxStore

ib = InMemoryInboxStore()
if not ib.mark_if_new("provider-evt-abc", ttl_seconds=86400):
    return 200  # duplicate
```

Notes:
- In-memory stores are for tests/local dev; implement SQL/Redis for production with row locks and `SKIP LOCKED` (or Lua) as needed.
