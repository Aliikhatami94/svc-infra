# Rate Limiting & Abuse Protection

This guide shows how to enable and tune the built-in rate limiter and request-size guard, and how to hook simple metrics for abuse detection.

## Features

- Global middleware-based rate limiting with standard headers
- Per-route dependency for fine-grained limits
- 429 responses include `Retry-After`
- Pluggable store interface (in-memory provided; Redis store available)
- Request size limit middleware returning 413
- Metrics hooks for rate-limiting events and suspect payloads

## Global middleware

```python
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=120,   # requests
    window=60,   # seconds
    key_fn=lambda r: r.headers.get("X-API-Key") or r.client.host,
)
```

Responses include headers:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset` (epoch seconds)

When exceeded, responses are 429 with `Retry-After` and the same headers.

Advanced options:
- `scope_by_tenant=True` to automatically include tenant id in the key if tenancy is configured.
- `limit_resolver=request -> int | None` to override the limit dynamically per request (e.g., per-plan quotas).

## Per-route dependency

```python
from fastapi import Depends
from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter

limiter = rate_limiter(limit=10, window=60, key_fn=lambda r: r.client.host)

@app.get("/resource", dependencies=[Depends(limiter)])
def get_resource():
    return {"ok": True}
```

The dependency supports the same options as the middleware: `scope_by_tenant`, `limit_resolver`, and a custom `store`.

## Store interface

The limiter uses a store abstraction so you can inject Redis or other backends.

- Default: `InMemoryRateLimitStore` (best-effort, single-process)
- Interface: `RateLimitStore` with `incr(key, window) -> (count, limit, resetEpoch)`

### Redis store

Use `RedisRateLimitStore` for multi-instance deployments. It implements a fixed-window counter
with atomic increments and sets expiry to the end of the window.

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

- Returns 413 with a Problem+JSON-like structure when `Content-Length` exceeds `max_bytes`.

## Metrics hooks

Hooks live in `svc_infra.obs.metrics` and are no-ops by default. Assign them to log or emit metrics.

```python
import logging
import svc_infra.obs.metrics as metrics

logger = logging.getLogger(__name__)

metrics.on_rate_limit_exceeded = lambda key, limit, retry: logger.warning(
    "rate_limited", extra={"key": key, "limit": limit, "retry_after": retry}
)

metrics.on_suspect_payload = lambda path, size: logger.warning(
    "suspect_payload", extra={"path": path, "size": size}
)
```

## Tuning tips

- Prefer API key or user ID for `key_fn`; fall back to IP if unauthenticated.
- Keep windows small (e.g., 60s); layer multiple limits when needed.
- For distributed deployments, use `RedisRateLimitStore` for atomic increments.
- Consider separate limits for read vs write routes.
- Combine with request size limits and auth lockout for layered defense.

## Related

- Timeouts & Resource Limits: `./timeouts-and-resource-limits.md` — complements rate limits by bounding slow uploads, long handlers, and downstream timeouts.

## Testing

- Use `-m ratelimit` to select rate-limiting tests.
- `-m security` also includes these in this repo by default.
