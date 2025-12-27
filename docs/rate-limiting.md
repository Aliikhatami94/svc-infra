# Rate Limiting & Abuse Protection

svc-infra provides production-ready rate limiting with multiple enforcement strategies,
pluggable storage backends, and abuse detection primitives.

---

## Quick Start

### Global Middleware

Apply rate limits to all endpoints:

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

app = FastAPI()
app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=120,   # requests per window
    window=60,   # window in seconds
)
```

### Per-Route Limits

Apply different limits to specific endpoints:

```python
from fastapi import Depends
from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter

# Strict limit for expensive operations
expensive_limiter = rate_limiter(limit=10, window=60)

@app.post("/api/generate", dependencies=[Depends(expensive_limiter)])
async def generate():
    return {"result": "..."}

# Relaxed limit for read operations  
read_limiter = rate_limiter(limit=1000, window=60)

@app.get("/api/items", dependencies=[Depends(read_limiter)])
async def list_items():
    return {"items": [...]}
```

---

## How It Works

### Fixed-Window Algorithm

The default algorithm uses fixed time windows:

```
Window 1 (0-60s)     Window 2 (60-120s)
├──────────────────┼──────────────────┤
│ Request 1-120    │ Counter resets   │
│ 121st → 429      │ Request 1-120 OK │
└──────────────────┴──────────────────┘
```

**Pros:**
- Simple, low overhead
- Easy to reason about
- Works well with Redis

**Cons:**
- Potential burst at window boundary (up to 2x limit in 2 seconds)

### Sliding Window (Future)

For smoother limits, sliding window or token bucket can be implemented.
The current fixed-window is sufficient for most use cases.

---

## Configuration Options

### Middleware Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 120 | Maximum requests per window |
| `window` | int | 60 | Window duration in seconds |
| `key_fn` | callable | API key or IP | Function to extract rate limit key from request |
| `store` | RateLimitStore | InMemory | Storage backend for counters |
| `skip_paths` | list[str] | [] | Paths to skip (prefix matching) |
| `scope_by_tenant` | bool | False | Include tenant ID in rate limit key |
| `limit_resolver` | callable | None | Dynamic limit based on request/tenant |
| `allow_untrusted_tenant_header` | bool | False | Trust X-Tenant-Id header (security risk!) |

### Key Function Examples

```python
# By API key (preferred for authenticated APIs)
key_fn = lambda r: r.headers.get("X-API-Key") or "anonymous"

# By user ID from JWT
key_fn = lambda r: getattr(r.state, "user_id", r.client.host)

# By IP address (fallback)
key_fn = lambda r: r.client.host if r.client else "unknown"

# Composite key
key_fn = lambda r: f"{r.headers.get('X-API-Key')}:{r.url.path}"
```

---

## Response Headers

All responses include rate limit information:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `Retry-After` | Seconds until rate limit resets (only on 429) |

### 429 Response Format

```json
{
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded.",
  "code": "RATE_LIMITED"
}
```

---

## Storage Backends

### InMemoryRateLimitStore

Default store for single-instance deployments:

```python
from svc_infra.api.fastapi.middleware.ratelimit_store import InMemoryRateLimitStore

store = InMemoryRateLimitStore(limit=120)
app.add_middleware(SimpleRateLimitMiddleware, limit=120, window=60, store=store)
```

**Warning**: Not suitable for production multi-instance deployments.
Data is lost on restart and not shared between instances.

### RedisRateLimitStore

Production-ready store with atomic operations:

```python
import redis
from svc_infra.api.fastapi.middleware.ratelimit_store import RedisRateLimitStore

redis_client = redis.Redis.from_url("redis://localhost:6379/0")
store = RedisRateLimitStore(redis_client, limit=120, prefix="rl")

app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=120,
    window=60,
    store=store,
)
```

**Features:**
- Atomic INCR with automatic expiry
- Shared across all instances
- Survives restarts
- Namespace support with prefix

### Backend Comparison

| Feature | InMemory | Redis |
|---------|----------|-------|
| Multi-instance | ❌ | ✅ |
| Persistence | ❌ | ✅ |
| Latency | ~0ms | ~1-5ms |
| Production ready | ❌ | ✅ |
| Setup complexity | None | Low |

---

## Per-Tenant Rate Limits

### Automatic Tenant Scoping

```python
app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=1000,
    window=60,
    scope_by_tenant=True,  # Each tenant gets their own bucket
)
```

This creates separate rate limit buckets per tenant:
- `api-key-123:tenant:tenant_abc` → 1000 req/min
- `api-key-123:tenant:tenant_xyz` → 1000 req/min

### Dynamic Limits by Plan

Different limits for different subscription tiers:

```python
async def get_limit_for_request(request, tenant_id):
    """Resolve rate limit based on tenant's plan."""
    if not tenant_id:
        return 100  # Anonymous/free tier

    plan = await get_tenant_plan(tenant_id)
    return {
        "free": 100,
        "starter": 1000,
        "pro": 10000,
        "enterprise": None,  # Unlimited
    }.get(plan, 100)

app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=100,  # Default fallback
    window=60,
    scope_by_tenant=True,
    limit_resolver=get_limit_for_request,
)
```

### Security: Untrusted Headers

**Never enable `allow_untrusted_tenant_header=True` unless you have a trusted proxy.**

```python
# ❌ DANGEROUS: Attackers can spoof X-Tenant-Id to evade limits
app.add_middleware(
    SimpleRateLimitMiddleware,
    allow_untrusted_tenant_header=True,  # DON'T DO THIS
)

# ✅ SAFE: Tenant ID resolved from authenticated session only
app.add_middleware(
    SimpleRateLimitMiddleware,
    scope_by_tenant=True,  # Uses resolve_tenant_id() from auth
)
```

---

## Cost-Based Rate Limiting

For APIs where some operations are more expensive:

```python
from dataclasses import dataclass

@dataclass
class CostTracker:
    costs = {"generate": 10, "search": 2, "read": 1}

    def get_cost(self, path: str) -> int:
        for pattern, cost in self.costs.items():
            if pattern in path:
                return cost
        return 1

cost_tracker = CostTracker()

# Custom key function that includes operation cost
def cost_aware_key(request):
    base_key = request.headers.get("X-API-Key", request.client.host)
    cost = cost_tracker.get_cost(request.url.path)
    # Record multiple "hits" for expensive operations
    return f"{base_key}:{cost}"
```

Alternative: Use different limiters per route category:

```python
# Expensive operations: 10 per minute
expensive = rate_limiter(limit=10, window=60)

# Normal operations: 100 per minute  
normal = rate_limiter(limit=100, window=60)

# Cheap operations: 1000 per minute
cheap = rate_limiter(limit=1000, window=60)

@app.post("/generate", dependencies=[Depends(expensive)])
async def generate(): ...

@app.get("/search", dependencies=[Depends(normal)])
async def search(): ...

@app.get("/items/{id}", dependencies=[Depends(cheap)])
async def get_item(id: str): ...
```

---

## Burst Handling

### Allowing Bursts

For APIs that need to handle traffic spikes:

```python
# Layer 1: Per-second burst limit
burst_limiter = rate_limiter(limit=20, window=1)

# Layer 2: Per-minute sustained limit
sustained_limiter = rate_limiter(limit=100, window=60)

@app.get("/api/data", dependencies=[
    Depends(burst_limiter),      # Max 20 req/sec
    Depends(sustained_limiter),  # Max 100 req/min
])
async def get_data():
    return {"data": "..."}
```

### Token Bucket Pattern (Manual)

For more sophisticated burst handling:

```python
import time
from dataclasses import dataclass

@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = None
    last_refill: float = None

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

---

## DDoS Protection Patterns

### Layered Defense

```python
# Layer 1: Request size limit (early rejection)
from svc_infra.api.fastapi.middleware.request_size_limit import RequestSizeLimitMiddleware
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=1_000_000)

# Layer 2: Global rate limit (IP-based)
app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=1000,
    window=60,
    key_fn=lambda r: r.client.host,
)

# Layer 3: Per-route limits (stricter for expensive endpoints)
expensive = rate_limiter(limit=10, window=60)
```

### Skip Paths

Exclude health checks and internal endpoints:

```python
app.add_middleware(
    SimpleRateLimitMiddleware,
    limit=100,
    window=60,
    skip_paths=[
        "/health",
        "/ready",
        "/metrics",
        "/_ops/",
    ],
)
```

### Request Size Guard

Block oversized payloads early:

```python
from svc_infra.api.fastapi.middleware.request_size_limit import RequestSizeLimitMiddleware

app.add_middleware(RequestSizeLimitMiddleware, max_bytes=1_000_000)  # 1MB
```

Returns 413 with Problem+JSON:

```json
{
  "title": "Payload Too Large",
  "status": 413,
  "detail": "Request body exceeds 1000000 bytes."
}
```

---

## Metrics and Monitoring

### Rate Limit Events

Hook into rate limit events for monitoring:

```python
import logging
import svc_infra.obs.metrics as metrics

logger = logging.getLogger(__name__)

# Log when clients hit rate limits
metrics.on_rate_limit_exceeded = lambda key, limit, retry: logger.warning(
    "rate_limited",
    extra={"key": key, "limit": limit, "retry_after": retry}
)

# Track in Prometheus
from prometheus_client import Counter

rate_limit_counter = Counter(
    "rate_limit_exceeded_total",
    "Total rate limit violations",
    ["key_prefix"]
)

def track_rate_limit(key, limit, retry):
    prefix = key.split(":")[0] if ":" in key else key[:20]
    rate_limit_counter.labels(key_prefix=prefix).inc()

metrics.on_rate_limit_exceeded = track_rate_limit
```

### Suspect Payload Detection

```python
# Log unusually large payloads
metrics.on_suspect_payload = lambda path, size: logger.warning(
    "suspect_payload",
    extra={"path": path, "size": size}
)
```

---

## Testing Rate Limits

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_rate_limit_enforced(client):
    # Make requests up to limit
    for i in range(120):
        response = client.get("/api/resource")
        assert response.status_code == 200
        assert "X-RateLimit-Remaining" in response.headers

    # Next request should be rate limited
    response = client.get("/api/resource")
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["code"] == "RATE_LIMITED"

def test_rate_limit_headers(client):
    response = client.get("/api/resource")

    assert response.headers["X-RateLimit-Limit"] == "120"
    assert int(response.headers["X-RateLimit-Remaining"]) <= 119
    assert response.headers["X-RateLimit-Reset"].isdigit()

def test_rate_limit_reset(client, time_machine):
    # Exhaust limit
    for _ in range(120):
        client.get("/api/resource")

    # Should be rate limited
    assert client.get("/api/resource").status_code == 429

    # Advance time past window
    time_machine.move_to(datetime.now() + timedelta(seconds=61))

    # Should be allowed again
    assert client.get("/api/resource").status_code == 200
```

### Load Testing

```bash
# Using wrk
wrk -t4 -c100 -d30s http://localhost:8000/api/resource

# Using hey
hey -n 10000 -c 50 http://localhost:8000/api/resource
```

---

## Best Practices

### Key Selection

1. **Authenticated APIs**: Use API key or user ID
2. **Public APIs**: Use IP address with care (NAT, proxies)
3. **Mixed**: Try API key first, fall back to IP

```python
key_fn = lambda r: (
    r.headers.get("X-API-Key")
    or getattr(r.state, "user_id", None)
    or r.client.host
)
```

### Window Size

| Use Case | Recommended Window |
|----------|-------------------|
| Real-time APIs | 1-10 seconds |
| Standard APIs | 60 seconds |
| Batch operations | 300-3600 seconds |

### Limit Values

| Tier | Typical Limit (per minute) |
|------|---------------------------|
| Anonymous | 10-50 |
| Free | 100-500 |
| Starter | 500-1000 |
| Pro | 1000-5000 |
| Enterprise | 10000+ or unlimited |

---

## See Also

- [Timeouts & Resource Limits](timeouts-and-resource-limits.md) — Complement rate limits with timeout controls
- [Idempotency](idempotency.md) — Handle retries safely after rate limiting
- [Observability](observability.md) — Monitor rate limit metrics
- [Tenancy](tenancy.md) — Per-tenant rate limiting patterns
