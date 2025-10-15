# Rate Limiting & Abuse Protection

This document explains how to use and tune the built-in rate limiting and request-size guard. It also covers simple metrics hooks for abuse detection.

## Features
- Global middleware-based rate limiting with standard headers
- Per-route dependency for fine-grained limits
- 429 responses include `Retry-After` (and `X-RateLimit-*` with middleware)
- Pluggable store interface (in-memory provided; Redis store available)
- Request size limit middleware returning 413
- Metrics hooks for rate limiting and suspect payloads

## Global middleware
```python
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=120,     # requests
    window=60,     # seconds
    key_fn=lambda r: r.headers.get("X-API-Key") or r.client.host,
    # store=RedisRateLimitStore(...),  # optional: see Redis section below
)
```
Responses include:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset` (epoch seconds)

On exceed: 429 with `Retry-After` and the same headers.

## Per-route dependency
```python
from fastapi import Depends
from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter

limiter = rate_limiter(limit=10, window=60, key_fn=lambda r: r.client.host)

@app.get("/resource", dependencies=[Depends(limiter)])
def get_resource():
    ...
```

Note: the dependency raises 429 with a `Retry-After` header when exceeded.

## Store interface
The limiter uses a store abstraction so you can swap in Redis or another backend.
- Default: `InMemoryRateLimitStore` (best-effort, single-process)
- Interface: `RateLimitStore` with `incr(key, window) -> (count, limit, resetEpoch)`

### Redis store
Use `RedisRateLimitStore` for multi-instance deployments. It implements a fixed-window counter
with atomic `INCR` and sets expiry to the end of the window.

```python
import redis
from svc_infra.api.fastapi.middleware.ratelimit_store import RedisRateLimitStore
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

r = redis.Redis.from_url("redis://localhost:6379/0")
store = RedisRateLimitStore(r, limit=120, prefix="rl")

app.add_middleware(SimpleRateLimitMiddleware, limit=120, window=60, store=store)
```

Notes:
- Fixed-window counters are simple and usually sufficient. For smoother limits, consider
  sliding window or token bucket in a future iteration.
- Use a namespace/prefix per environment/tenant if needed.

## Request size guard
```python
from svc_infra.api.fastapi.middleware.request_size_limit import RequestSizeLimitMiddleware

app.add_middleware(RequestSizeLimitMiddleware, max_bytes=1_000_000)
```
- Returns 413 with a small JSON body when Content-Length exceeds max.

## Metrics hooks
Hooks live in `svc_infra.obs.metrics` and are no-ops by default. Assign them to log or emit metrics.

```python
import svc_infra.obs.metrics as metrics

metrics.on_rate_limit_exceeded = lambda key, limit, retry: logger.warning(
    "rate_limited", extra={"key": key, "limit": limit, "retry_after": retry}
)
metrics.on_suspect_payload = lambda path, size: logger.warning(
    "suspect_payload", extra={"path": path, "size": size}
)
```

## Tuning tips
- Use API key or user ID for `key_fn`; fallback to IP if unauthenticated.
- Keep window small (e.g., 60s) and layer multiple limits if needed.
- For distributed deployments, use the Redis `RateLimitStore` for atomic increments.
- Consider separate limits for read vs write routes.
- Combine with request size limits and auth lockout for layered defense.

## Testing
- Marker `-m ratelimit` selects rate limiting tests.
- Marker `-m security` also includes these by default in this repo.
