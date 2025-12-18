# Migration Guide

This guide documents breaking changes and migration paths between versions of svc-infra.

## Version Compatibility

| svc-infra | Python | Notes |
|-----------|--------|-------|
| 0.1.x | 3.11+ | Current stable |
| 0.2.x (planned) | 3.11+ | API refinements |

## Migrating to 0.1.x

### From Custom Infrastructure

If you're migrating from custom auth/cache/jobs implementation:

#### Authentication

```python
# Before (custom)
from myapp.auth import verify_token, get_user

@app.get("/protected")
def protected(user = Depends(get_user)):
    ...

# After (svc-infra)
from svc_infra.auth import RequireUser

@app.get("/protected")
def protected(user = RequireUser()):
    ...
```

#### Caching

```python
# Before (custom Redis wrapper)
from myapp.cache import redis_client

async def get_data(key: str):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    data = await fetch_data()
    await redis_client.setex(key, 3600, json.dumps(data))
    return data

# After (svc-infra)
from svc_infra.cache import cache_read, cache_write

async def get_data(key: str):
    cached = await cache_read(key)
    if cached:
        return cached
    data = await fetch_data()
    await cache_write(key, data, ttl=3600)
    return data
```

#### Background Jobs

```python
# Before (custom Celery/RQ)
@celery_app.task
def send_email(to, subject, body):
    ...

# After (svc-infra)
from svc_infra.jobs import easy_jobs

jobs = easy_jobs(backend="redis")

@jobs.task
async def send_email(to: str, subject: str, body: str):
    ...
```

## Planned Breaking Changes (0.2.x)

### Router Rename

```python
# 0.1.x
from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.api.fastapi.dual.protected import user_router

# 0.2.x (planned)
from svc_infra.routers import public_router, user_router
```

### Cache API Simplification

```python
# 0.1.x
from svc_infra.cache import cache_read, cache_write

# 0.2.x (planned) - decorator-based
from svc_infra.cache import cached

@cached(ttl=3600)
async def get_user(user_id: str):
    return await db.get_user(user_id)
```

## Deprecation Notices

### 0.1.50+

- `easy_service_app()` parameters simplified
- `add_observability()` now auto-configures based on environment

### 0.1.100+

- Old cache backend names deprecated (use "redis", "memory")
- Legacy auth decorators deprecated (use dependency injection)

## Getting Help

- Check the [error handling guide](error-handling.md) for exception changes
- Open an issue for migration questions
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
