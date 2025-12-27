# Caching Guide

High-performance caching with Redis and in-memory backends using the cashews library.

## Overview

svc-infra provides a comprehensive caching layer:

- **Multiple Backends**: Redis for production, in-memory for development/testing
- **Decorator-Based API**: `@cache_read` and `@cache_write` for easy caching
- **Resource Helpers**: Entity-based caching with `resource()` for standardized key patterns
- **TTL Management**: Configurable TTL buckets (short, default, long)
- **Cache Invalidation**: Tag-based invalidation with automatic recaching
- **FastAPI Integration**: One-liner `add_cache(app)` with lifecycle management

## Quick Start

### Basic Setup

```python
from svc_infra.cache import cache_read, cache_write, init_cache

# Initialize cache (uses CACHE_URL env var or defaults to memory)
init_cache()

@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

@cache_write(tags=["user:{user_id}"])
async def update_user(user_id: int, data: dict):
    await db.update_user(user_id, data)
    return data
```

### FastAPI Integration

```python
from fastapi import FastAPI
from svc_infra.cache import add_cache, cache_read

app = FastAPI()

# Wire cache lifecycle (startup/shutdown)
add_cache(app)

@app.get("/users/{user_id}")
@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    return await fetch_user_from_db(user_id)
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_URL` | — | Cache backend URL (Redis or memory) |
| `REDIS_URL` | — | Fallback if `CACHE_URL` not set |
| `CACHE_PREFIX` | `svc` | Namespace prefix for all cache keys |
| `CACHE_VERSION` | `v1` | Version suffix for cache key namespacing |
| `CACHE_TTL_DEFAULT` | `300` | Default TTL in seconds (5 minutes) |
| `CACHE_TTL_SHORT` | `30` | Short TTL in seconds (30 seconds) |
| `CACHE_TTL_LONG` | `3600` | Long TTL in seconds (1 hour) |

### Backend URLs

```bash
# Redis (production)
CACHE_URL=redis://localhost:6379/0
CACHE_URL=redis://user:password@redis.example.com:6379/0
CACHE_URL=rediss://redis.example.com:6379/0  # TLS

# In-memory (development/testing)
CACHE_URL=mem://
```

### Programmatic Configuration

```python
from svc_infra.cache import add_cache, init_cache

# Option 1: With FastAPI app
add_cache(
    app,
    url="redis://localhost:6379/0",
    prefix="myapp",
    version="v2",
)

# Option 2: Standalone initialization
init_cache(
    url="redis://localhost:6379/0",
    prefix="myapp",
    version="v1",
)
```

---

## Decorator Patterns

### `@cache_read` - Caching Read Operations

Cache function results with automatic key generation:

```python
from svc_infra.cache import cache_read

# Basic usage with key template
@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

# Multiple parameters in key
@cache_read(key="org:{org_id}:user:{user_id}", ttl=600)
async def get_org_user(org_id: int, user_id: int):
    return await db.fetch_org_user(org_id, user_id)

# Tuple key format (auto-converted to template)
@cache_read(key=("user", "profile", "{user_id}"), ttl=300)
async def get_user_profile(user_id: int):
    return await db.fetch_profile(user_id)
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | `str \| tuple[str, ...]` | Cache key template with `{param}` placeholders |
| `ttl` | `int` | Time to live in seconds (defaults to `CACHE_TTL_DEFAULT`) |
| `tags` | `Iterable[str]` | Cache tags for invalidation (defaults to key template) |
| `early_ttl` | `int` | Early expiration for cache warming |
| `refresh` | `bool` | Whether to refresh cache on access |

### `@cache_write` - Invalidating on Writes

Invalidate cache tags after write operations:

```python
from svc_infra.cache import cache_write

@cache_write(tags=["user:{user_id}"])
async def update_user(user_id: int, data: dict):
    return await db.update_user(user_id, data)

# Multiple tags
@cache_write(tags=["user:{user_id}", "org:{org_id}:users"])
async def update_user_org(user_id: int, org_id: int, data: dict):
    return await db.update_user(user_id, data)
```

#### Dynamic Tags

```python
from svc_infra.cache import cache_write

def get_user_tags(user_id: int, **kwargs) -> list[str]:
    return [f"user:{user_id}", f"user:{user_id}:profile"]

@cache_write(tags=get_user_tags)
async def update_user(user_id: int, data: dict):
    return await db.update_user(user_id, data)
```

### Recaching After Invalidation

Warm the cache immediately after invalidation:

```python
from svc_infra.cache import cache_read, cache_write, recache

@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

@cache_write(
    tags=["user:{user_id}"],
    recache=[recache(get_user, include=["user_id"])]
)
async def update_user(user_id: int, data: dict):
    await db.update_user(user_id, data)
    return data
```

#### Recache Options

```python
from svc_infra.cache import recache

# Include specific parameters
recache(get_user, include=["user_id"])

# Rename parameters
recache(get_org_user, rename={"user_id": "id"})

# Add extra parameters
recache(get_user_with_options, extra={"include_deleted": False})

# Combine options
recache(
    get_user_details,
    include=["user_id"],
    extra={"expand": True},
)
```

---

## Resource Helper

The `resource()` helper provides entity-based caching with standardized key patterns:

```python
from svc_infra.cache import resource

# Define a resource
user = resource("user", "user_id")

@user.cache_read(suffix="profile", ttl=300)
async def get_user_profile(user_id: int):
    # Key: user:profile:{user_id}
    # Tags: ["user:{user_id}"]
    return await db.fetch_profile(user_id)

@user.cache_read(suffix="settings", ttl=600)
async def get_user_settings(user_id: int):
    # Key: user:settings:{user_id}
    return await db.fetch_settings(user_id)

@user.cache_write()
async def update_user(user_id: int, data: dict):
    # Invalidates all user:{user_id} tagged entries
    return await db.update_user(user_id, data)
```

### Resource with Recaching

```python
user = resource("user", "user_id")

@user.cache_write(
    recache=[
        (get_user_profile, lambda user_id, **_: {"user_id": user_id}),
        (get_user_settings, lambda user_id, **_: {"user_id": user_id}),
    ],
    recache_max_concurrency=3,
)
async def update_user(user_id: int, data: dict):
    return await db.update_user(user_id, data)
```

### Custom Key Templates

```python
user = resource("user", "user_id")

@user.cache_read(
    suffix="profile",
    ttl=300,
    key_template="v2:user:{user_id}:profile",  # Custom key
    tags_template=("user:{user_id}", "profiles"),  # Custom tags
)
async def get_user_profile_v2(user_id: int):
    return await db.fetch_profile(user_id)
```

---

## TTL Strategies

### Built-in TTL Buckets

```python
from svc_infra.cache.ttl import TTL_SHORT, TTL_DEFAULT, TTL_LONG

# Short-lived data (30 seconds) - rate limits, sessions
@cache_read(key="rate:{ip}", ttl=TTL_SHORT)
async def get_rate_limit(ip: str): ...

# Default TTL (5 minutes) - most data
@cache_read(key="user:{user_id}", ttl=TTL_DEFAULT)
async def get_user(user_id: int): ...

# Long-lived data (1 hour) - config, static content
@cache_read(key="config:{key}", ttl=TTL_LONG)
async def get_config(key: str): ...
```

### Environment-Based TTL

```bash
# Override defaults via environment
CACHE_TTL_DEFAULT=600   # 10 minutes
CACHE_TTL_SHORT=15      # 15 seconds
CACHE_TTL_LONG=7200     # 2 hours
```

### TTL by Data Type

| Data Type | Recommended TTL | Rationale |
|-----------|----------------|-----------|
| Session data | 30s - 60s | Needs freshness for security |
| User profiles | 5m - 15m | Rarely changes, but should reflect updates |
| Configuration | 1h - 24h | Changes infrequently |
| Rate limits | 1s - 60s | Must be accurate for enforcement |
| Search results | 5m - 30m | Can be slightly stale |
| Static content | 1h - 24h | Rarely changes |

---

## Caching Strategies

### Cache-Aside Pattern (Default)

The default pattern - check cache first, fetch on miss:

```python
@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    # Called only on cache miss
    return await db.fetch_user(user_id)
```

### Write-Through Pattern

Update cache and database together:

```python
@cache_write(
    tags=["user:{user_id}"],
    recache=[recache(get_user, include=["user_id"])]
)
async def update_user(user_id: int, data: dict):
    # 1. Update database
    result = await db.update_user(user_id, data)
    # 2. Invalidate old cache (via tags)
    # 3. Warm cache with new data (via recache)
    return result
```

### Cache Stampede Prevention

Use locking to prevent multiple simultaneous cache rebuilds:

```python
user = resource("user", "user_id")

@user.cache_read(suffix="profile", ttl=300, lock=True)
async def get_user_profile(user_id: int):
    # Only one request will hit the DB; others wait for cache
    return await expensive_db_query(user_id)
```

### Graceful Degradation

Handle cache failures gracefully:

```python
from svc_infra.cache import get_cache
import logging

logger = logging.getLogger(__name__)

async def get_user_with_fallback(user_id: int):
    cache = get_cache()
    key = f"user:{user_id}"

    try:
        cached = await cache.get(key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")

    # Fallback to database
    user = await db.fetch_user(user_id)

    try:
        await cache.set(key, user, ttl=300)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    return user
```

---

## Cache Invalidation

### Tag-Based Invalidation

```python
from svc_infra.cache import cache_write

# All entries tagged with "user:{user_id}" are invalidated
@cache_write(tags=["user:{user_id}"])
async def update_user(user_id: int, data: dict):
    return await db.update_user(user_id, data)

# Invalidate multiple tag patterns
@cache_write(tags=["user:{user_id}", "org:{org_id}:members"])
async def remove_user_from_org(user_id: int, org_id: int):
    return await db.remove_from_org(user_id, org_id)
```

### Manual Invalidation

```python
from svc_infra.cache import get_cache

async def invalidate_user_cache(user_id: int):
    cache = get_cache()
    # Delete specific key
    await cache.delete(f"user:{user_id}")

    # Delete by pattern (Redis only)
    await cache.delete_match(f"user:{user_id}:*")
```

### Event-Driven Invalidation

Integrate with webhooks or message queues:

```python
from svc_infra.cache import get_cache

async def handle_user_updated_event(event: dict):
    user_id = event["user_id"]
    cache = get_cache()

    # Invalidate all user-related cache entries
    await cache.delete_match(f"user:{user_id}:*")
```

---

## Direct Cache Access

Access the underlying cache instance for advanced operations:

```python
from svc_infra.cache import get_cache

async def advanced_cache_ops():
    cache = get_cache()

    # Basic operations
    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")
    await cache.delete("key")

    # Check existence
    exists = await cache.exists("key")

    # Set if not exists
    await cache.set("key", "value", exist=False)

    # Get and delete (pop)
    value = await cache.get_delete("key")

    # Increment/decrement
    await cache.incr("counter")
    await cache.incr("counter", 5)

    # Pattern deletion (Redis)
    await cache.delete_match("user:*:profile")
```

### App State Access

When using `add_cache(app)`:

```python
from fastapi import FastAPI, Request

app = FastAPI()
add_cache(app)

@app.get("/stats")
async def get_stats(request: Request):
    cache = request.app.state.cache
    # Use cache directly
    return await cache.get("stats")
```

---

## Production Recommendations

### Redis Configuration

```bash
# Production Redis settings
CACHE_URL=redis://redis.example.com:6379/0

# With authentication
CACHE_URL=redis://user:password@redis.example.com:6379/0

# With TLS
CACHE_URL=rediss://redis.example.com:6379/0
```

### Redis Cluster

For high availability, use Redis Cluster:

```bash
# Redis Cluster (comma-separated nodes)
CACHE_URL=redis://node1:6379,node2:6379,node3:6379/0
```

### Memory Limits

Configure Redis maxmemory:

```bash
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Eviction Policies

| Policy | Use Case |
|--------|----------|
| `allkeys-lru` | General caching - evict least recently used |
| `allkeys-lfu` | Hot data caching - evict least frequently used |
| `volatile-ttl` | TTL-based eviction of expiring keys first |
| `noeviction` | Don't evict (returns error when full) |

### Connection Pooling

The cache backend uses connection pooling by default. For high-throughput:

```python
# Redis connection pool is managed by cashews
# No additional configuration needed for most use cases
```

### Monitoring Cache Performance

```python
from svc_infra.cache import get_cache

async def cache_health_check():
    cache = get_cache()
    try:
        await cache.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

---

## Testing

### In-Memory Backend

Use memory backend for tests:

```python
import pytest
from svc_infra.cache import init_cache, cache_read

@pytest.fixture(autouse=True)
def setup_cache():
    init_cache(url="mem://", prefix="test", version="v1")
    yield

@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    return {"id": user_id, "name": "Test User"}

async def test_cache_read():
    # First call - cache miss
    result1 = await get_user(1)
    assert result1["id"] == 1

    # Second call - cache hit
    result2 = await get_user(1)
    assert result2 == result1
```

### Mocking Cache

```python
from unittest.mock import AsyncMock, patch

async def test_with_mocked_cache():
    with patch("svc_infra.cache.get_cache") as mock_cache:
        mock_cache.return_value.get = AsyncMock(return_value={"id": 1})
        mock_cache.return_value.set = AsyncMock()

        # Your test code here
```

---

## Troubleshooting

### Stale Data

```
Cache returns outdated data after updates
```

**Solutions:**
1. Ensure `@cache_write` is applied to all mutation endpoints
2. Verify tag patterns match between read and write decorators
3. Check TTL is appropriate for your use case

### Connection Issues

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions:**
1. Verify `CACHE_URL` or `REDIS_URL` is correct
2. Check Redis is running and accessible
3. Verify network/firewall allows connection
4. Check Redis authentication credentials

### High Memory Usage

```
Redis using excessive memory
```

**Solutions:**
1. Review TTL values - reduce for frequently changing data
2. Configure `maxmemory` and eviction policy
3. Audit cache key patterns for cardinality
4. Use `delete_match` to clean up stale keys

### Cache Stampede

```
Multiple simultaneous requests hitting database
```

**Solutions:**
1. Use `lock=True` in `resource().cache_read()`
2. Implement cache warming on startup
3. Use `early_ttl` for background refresh

### Key Collisions

```
Cache returning wrong data
```

**Solutions:**
1. Ensure unique cache key templates
2. Include all relevant parameters in key
3. Use `CACHE_VERSION` for breaking changes
4. Verify `CACHE_PREFIX` is unique per environment

---

## See Also

- [Jobs Guide](jobs.md) - Background job processing
- [Environment Reference](environment.md) - All cache environment variables
- [Resilience Patterns](resilience.md) - Circuit breakers and fallbacks
- [Observability Guide](observability.md) - Monitoring cache performance
