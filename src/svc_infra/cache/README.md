# SVC Infra Cache 🚀

**One-button caching for your async Python applications.**

Stop writing boilerplate cache logic. This module provides production-ready decorators for Redis caching with automatic invalidation, recaching, and namespace management.

## Quick Start

### 1. Initialize Cache (Once per app)

```python
from svc_infra.cache import init_cache
import os

# Basic setup
init_cache()

# Production setup with Redis
init_cache(
    url="redis://localhost:6379",
    prefix=os.getenv("CACHE_PREFIX", "myapp"),
    version=os.getenv("CACHE_VERSION", "v1"),
)
```

### 2. Choose Your Style

## 🎯 **Option A: Resource Pattern (Recommended)**

Perfect for entity-based operations (users, products, orders, etc.)

```python
from svc_infra.cache import resource, TTL_LONG
import asyncio

# Create a resource manager
user = resource("user", "user_id")

# Cached read - automatically uses key "user:profile:{user_id}" and tag "user:{user_id}"
@user.cache_read(suffix="profile", ttl=TTL_LONG, smooth_expiry=True)
async def get_user_profile(*, user_id: int):  # Notice keyword-only parameter
    # Your database fetch logic here
    return await fetch_user_from_db(user_id)

# Cache write - automatically invalidates "user:{user_id}" tags
@user.cache_write()
async def update_user_profile(*, user_id: int, data: dict):
    # Your database save logic here
    return await save_user_to_db(user_id, data)

# Cache delete - automatically invalidates "user:{user_id}" tags
@user.cache_write()
async def delete_user_profile(*, user_id: int):
    # Your database delete logic here
    return await delete_user_from_db(user_id)
```

**That's it!** Cache invalidation happens automatically. No boilerplate needed.

## 🔧 **Option B: Manual Decorators (More Control)**

For custom cache keys and tags:

```python
from svc_infra.cache import cache_read, cache_write, TTL_LONG

# Cached read with custom key and tags
@cache_read(
    key="user:{user_id}:profile",
    ttl=TTL_LONG,
    tags=lambda *, user_id, **__: [f"user:{user_id}"],  # Use lambda, not literal strings!
    smooth_expiry=True,
)
async def get_user_profile(*, user_id: int):  # Keyword-only for cache stability
    return await fetch_user_from_db(user_id)

# Cache write with tag invalidation
@cache_write(
    tags=lambda *, user_id, **__: [f"user:{user_id}"],
)
async def update_user_profile(*, user_id: int, data: dict):
    return await save_user_to_db(user_id, data)
```

## 📊 **Production Features**

### Observability & Debug Mode

Enable detailed cache logging and metrics:

```bash
# Enable debug logs
export CACHE_DEBUG=1

# Enable metrics collection
export CACHE_METRICS=1
```

```python
from svc_infra.cache import get_metrics, reset_metrics

# Check cache performance
metrics = get_metrics()
print(f"Cache hits: {metrics['cache.hit']}")
print(f"Cache misses: {metrics['cache.miss']}")
print(f"Invalidations: {metrics['cache.invalidate.count']}")
print(f"Avg warm time: {metrics['cache.warm.ms']}ms")

# Reset metrics for new measurement period
reset_metrics()
```

Debug logs show detailed cache operations:
```
[HIT] key=user:123:profile duration_ms=2.1ms ttl=3600
[MISS] key=user:123:profile duration_ms=45.2ms ttl=3600 cause=cache_miss
[WARM] key=get_user_profile duration_ms=38.7ms params={'user_id': 123}
[INVALIDATE] key=tags=['user:123']
```

### Negative Caching (404 Handling)

Cache missing entities with short TTL to prevent hot 404s:

```python
from svc_infra.cache import negative_cache, is_negative_cache_result, unwrap_negative_cache_result

@user.cache_read(suffix="profile", ttl=TTL_LONG)
async def get_user_profile(*, user_id: int):
    user_data = await fetch_user_from_db(user_id)

    if user_data is None:
        # Cache the "not found" result for 60 seconds
        return negative_cache(ttl=60, value=None)

    return user_data

# In your API layer
async def api_get_user(user_id: int):
    result = await get_user_profile(user_id=user_id)

    if is_negative_cache_result(result):
        actual_value = unwrap_negative_cache_result(result)  # Returns None
        raise HTTPException(404, "User not found")

    return result
```

### Smooth Expiry (Prevent Cache Stampedes)

Automatically add jitter to prevent synchronized cache expirations:

```python
# Automatic jitter - TTL becomes 3600 ± 10% randomly
@cache_read(key="expensive:{id}", ttl=3600, smooth_expiry=True)
async def expensive_computation(*, id: str):
    return await heavy_calculation(id)

# Or manually specify early refresh
@cache_read(key="data:{id}", ttl=3600, early_ttl=3300)  # Refresh 5min early
async def get_data(*, id: str):
    return await fetch_data(id)
```

## 📖 Complete Examples

### Resource Pattern Example

```python
from svc_infra.cache import init_cache, resource, TTL_LONG
import asyncio, os

# 1. Initialize cache
init_cache(
    url="redis://localhost:6379",
    prefix=os.getenv("CACHE_PREFIX", "svc"),
    version=os.getenv("CACHE_VERSION", "v1"),
)

# 2. Mock database
_USERS: dict[int, dict] = {}

def _ensure_user(uid: int):
    _USERS.setdefault(uid, {"user_id": uid, "name": "John Doe"})

async def fetch_user(uid: int):
    if uid not in _USERS:
        raise KeyError(f"User {uid} not found")
    await asyncio.sleep(0.02)  # Simulate DB latency
    return dict(_USERS[uid])

async def save_user(uid: int, data: dict):
    _ensure_user(uid)
    await asyncio.sleep(0.02)
    _USERS[uid].update(data)
    return dict(_USERS[uid])

async def delete_user(uid: int):
    await asyncio.sleep(0.02)
    if uid in _USERS:
        del _USERS[uid]
        return True
    return False

# 3. Resource sugar - automatically handles keys and tags
user = resource("user", "user_id")

@user.cache_read(suffix="profile", ttl=TTL_LONG, smooth_expiry=True)
async def get_user_profile(*, user_id: int):  # Keyword-only enforced!
    print(f"🔥 Cache MISS - fetching user {user_id} from DB")
    return await fetch_user(user_id)

@user.cache_write()
async def update_user_profile(*, user_id: int, data: dict):
    print(f"💾 Updating user {user_id} and invalidating cache")
    return await save_user(user_id, data)

@user.cache_write()
async def delete_user_profile(*, user_id: int):
    print(f"🗑️ Deleting user {user_id} and invalidating cache")
    return await delete_user(user_id)

# 4. Demo
async def main():
    uid = 123
    _ensure_user(uid)  # Create initial user

    # First call - cache miss, hits DB
    p1 = await get_user_profile(user_id=uid)
    print("✅ Fetched profile:", p1)

    # Second call - cache hit, no DB call
    p1_cached = await get_user_profile(user_id=uid)
    print("⚡ Cached profile:", p1_cached)

    # Update - invalidates cache
    p2 = await update_user_profile(user_id=uid, data={"name": "New Name"})
    print("✅ Updated profile:", p2)

    # Third call - cache was invalidated, hits DB again
    p3 = await get_user_profile(user_id=uid)
    print("✅ Fresh profile:", p3)

    # Delete - invalidates cache
    deleted = await delete_user_profile(user_id=uid)
    print("✅ Deleted user:", deleted)

    # Try to fetch deleted user
    try:
        p4 = await get_user_profile(user_id=uid)
        print("❌ This shouldn't happen!")
    except KeyError as e:
        print(f"✅ User successfully deleted - {e}")

    # Check metrics
    from svc_infra.cache import get_metrics
    metrics = get_metrics()
    print(f"📊 Cache hits: {metrics.get('cache.hit', 0)}")
    print(f"📊 Cache misses: {metrics.get('cache.miss', 0)}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Manual Decorators Example

```python
from svc_infra.cache import init_cache, cache_read, cache_write, TTL_LONG
import asyncio, os

# 1. Cache init
init_cache(
    url="redis://localhost:6379",
    prefix=os.getenv("CACHE_PREFIX", "svc"),
    version=os.getenv("CACHE_VERSION", "v1"),
)

# 2. Mock database
_USERS: dict[int, dict] = {}

def _ensure_user(uid: int):
    _USERS.setdefault(uid, {"user_id": uid, "name": "John Doe"})

async def fetch_user_from_database(user_id: int):
    if user_id not in _USERS:
        raise KeyError(f"User {user_id} not found")
    await asyncio.sleep(0.02)
    print(f"🔥 DB FETCH - user {user_id}")
    return dict(_USERS[user_id])

async def save_user_to_database(user_id: int, data: dict):
    _ensure_user(user_id)
    await asyncio.sleep(0.02)
    _USERS[user_id].update(data)
    print(f"💾 DB SAVE - user {user_id}")
    return dict(_USERS[user_id])

# 3. Cached read with tags - IMPORTANT: Use lambda for dynamic tags!
@cache_read(
    key="user:{user_id}:profile",
    ttl=TTL_LONG,
    tags=lambda *, user_id, **__: [f"user:{user_id}"],  # Lambda prevents literal tag bugs
    smooth_expiry=True,
)
async def get_user_profile(*, user_id: int):  # Keyword-only for stability
    return await fetch_user_from_database(user_id)

# 4. Cache write with invalidation
@cache_write(
    tags=lambda *, user_id, **__: [f"user:{user_id}"],  # Same lambda pattern
)
async def update_user_profile(*, user_id: int, data: dict):
    return await save_user_to_database(user_id, data)

# 5. Demo
async def main():
    uid = 123
    _ensure_user(uid)

    p1 = await get_user_profile(user_id=uid)    # cold -> DB
    print("✅ Fetched profile:", p1)

    p1_again = await get_user_profile(user_id=uid)  # warm -> cache
    print("⚡ Cached profile:", p1_again)

    p2 = await update_user_profile(user_id=uid, data={"name": "New Name"})
    print("✅ Updated profile:", p2)

    p3 = await get_user_profile(user_id=uid)    # invalidated -> cold -> DB
    print("✅ Fresh profile:", p3)

    assert p3["name"] == "New Name"
    print("🎉 Cache invalidation worked!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🕒 TTL Options

```python
from svc_infra.cache import TTL_SHORT, TTL_DEFAULT, TTL_LONG

# Pre-defined TTLs
TTL_SHORT    # 30 seconds
TTL_DEFAULT  # 5 minutes  
TTL_LONG     # 1 hour

# Custom TTL with smooth expiry
@cache_read(key="data:{id}", ttl=600, smooth_expiry=True)  # 10 minutes ± jitter
async def get_data(*, id: str):
    return await fetch_data(id)
```

## 🔄 Advanced: Recaching

Automatically warm the cache after invalidation:

```python
from svc_infra.cache import cache_write, recache

@cache_write(
    tags=lambda *, user_id, **__: [f"user:{user_id}"],
    recache_specs=[  # Fixed parameter name (was "recache")
        recache(get_user_profile, include=["user_id"])
    ]
)
async def update_user_profile(*, user_id: int, data: dict):
    result = await save_user_to_db(user_id, data)
    # Cache is invalidated, then get_user_profile is called to warm it
    return result
```

## 🏷️ Cache Tags

Use tags to invalidate related cache entries:

```python
# Multiple tags
@cache_read(
    key="user:{user_id}:posts",
    tags=lambda *, user_id, **__: [f"user:{user_id}", "posts"]  # Lambda prevents bugs
)
async def get_user_posts(*, user_id: int):
    return await fetch_posts(user_id)

# Invalidate all user-related cache when user is deleted
@cache_write(tags=lambda *, user_id, **__: [f"user:{user_id}"])
async def delete_user(*, user_id: int):
    await remove_user_from_db(user_id)
```

## 🔧 Configuration

### Environment Variables

```bash
# Observability
CACHE_DEBUG=1           # Enable detailed debug logs
CACHE_METRICS=1         # Enable metrics collection

# Optional: Customize TTL values
CACHE_TTL_SHORT=30      # seconds
CACHE_TTL_DEFAULT=300   # seconds  
CACHE_TTL_LONG=3600     # seconds
```

### Redis URLs

```python
# Local Redis
init_cache(url="redis://localhost:6379")

# Redis with auth
init_cache(url="redis://user:pass@localhost:6379/0")

# Redis Cluster
init_cache(url="redis://localhost:7000,localhost:7001,localhost:7002")

# No Redis (in-memory only - for testing)
init_cache()
```

## 🚨 Common Patterns

### 1. List Operations

```python
product = resource("product", "product_id")

@product.cache_read(suffix="details", ttl=TTL_LONG, smooth_expiry=True)
async def get_product(*, product_id: int):
    return await db.fetch_product(product_id)

# Invalidate individual product
@product.cache_write()
async def update_product(*, product_id: int, data: dict):
    return await db.save_product(product_id, data)

# Invalidate all products in category
@cache_write(tags=lambda *, category_id, **__: [f"category:{category_id}"])
async def update_category(*, category_id: int, data: dict):
    await db.save_category(category_id, data)
    # This will invalidate all products tagged with this category
```

### 2. Complex Keys

```python
@cache_read(
    key="user:{user_id}:permissions:{role}",
    ttl=TTL_DEFAULT,
    tags=lambda *, user_id, role, **__: [f"user:{user_id}", f"role:{role}"],
    smooth_expiry=True,
)
async def get_user_permissions(*, user_id: int, role: str):
    return await fetch_permissions(user_id, role)
```

### 3. Hot 404 Prevention

```python
from svc_infra.cache import negative_cache, is_negative_cache_result

@cache_read(key="user:{user_id}", ttl=TTL_LONG)
async def get_user(*, user_id: int):
    user = await db.get_user(user_id)

    if user is None:
        # Cache the miss for 60 seconds to prevent hot 404s
        return negative_cache(ttl=60, value=None)

    return user

# In your API
async def api_get_user(user_id: int):
    result = await get_user(user_id=user_id)

    if is_negative_cache_result(result):
        raise HTTPException(404, "User not found")

    return result
```

## 🧪 Testing

```python
# Disable caching in tests
import os
os.environ["CACHE_TTL_DEFAULT"] = "0"  # No caching

# Or use separate cache namespace
init_cache(prefix="test", version="v1")

# Check metrics in tests
from svc_infra.cache import get_metrics, reset_metrics

def test_cache_behavior():
    reset_metrics()

    # Your test code here

    metrics = get_metrics()
    assert metrics["cache.hit"] > 0
    assert metrics["cache.miss"] > 0
```

## 🐛 Debugging

```python
import logging

# Enable cache debug logs
logging.getLogger("svc_infra.cache").setLevel(logging.DEBUG)

# Check metrics
from svc_infra.cache import get_metrics
metrics = get_metrics()
print(f"Hit ratio: {metrics['cache.hit'] / (metrics['cache.hit'] + metrics['cache.miss']):.2%}")

# Check what's in cache
from svc_infra.cache.backend import instance
cache = instance()
keys = await cache.get_many("user:*")  # Get all user cache keys
```

## ⚠️ Production Warnings

The cache system now warns you about common mistakes:

```python
# ❌ Bad: Literal tag strings (silent failures)
@cache_read(
    key="user:{user_id}",
    tags=["user:{user_id}"]  # This won't work! String is literal
)

# ✅ Good: Lambda for dynamic tags
@cache_read(
    key="user:{user_id}",
    tags=lambda *, user_id, **__: [f"user:{user_id}"]
)

# ❌ Bad: Positional ID parameters
async def get_user(user_id: int):  # Cache keys unstable

# ✅ Good: Keyword-only ID parameters
async def get_user(*, user_id: int):  # Cache keys stable
```

## 🎯 Best Practices

1. **Use resource pattern** for entity-based caching
2. **Use keyword-only arguments** (`*, user_id`) for cache key stability  
3. **Use lambdas for dynamic tags** to avoid literal string bugs
4. **Enable smooth_expiry** for high-traffic keys to prevent stampedes
5. **Use negative caching** for hot 404 scenarios
6. **Monitor metrics** in production (`CACHE_METRICS=1`)
7. **Enable debug logs** during development (`CACHE_DEBUG=1`)
8. **Namespace by environment** (`prod`, `staging`, `dev`)

## 🚀 Production Checklist

- ✅ Redis connection pooling configured
- ✅ Cache TTLs appropriate for your data
- ✅ Monitoring cache hit rates via metrics
- ✅ Debug logging enabled in development
- ✅ Smooth expiry enabled for high-traffic keys
- ✅ Negative caching for hot 404s
- ✅ Keyword-only parameters enforced
- ✅ Lambda tags used (not literal strings)
- ✅ Graceful fallback when cache is down
- ✅ Cache keys namespaced by environment
- ✅ Invalidation patterns tested

---

**Need help?** Check the source code in `svc_infra/cache/` or ask the team! 🙋‍♂️
