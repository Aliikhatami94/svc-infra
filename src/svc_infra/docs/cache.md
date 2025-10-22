# Cache guide

The cache module wraps [cashews](https://github.com/Krukov/cashews) with decorators and namespace helpers so services can centralize key formats.

```python
from svc_infra.cache import cache_read, cache_write, init_cache

init_cache()  # uses CACHE_PREFIX / CACHE_VERSION

@cache_read(key="user:{user_id}", ttl=300)
async def get_user(user_id: int):
    ...
```

### Environment

- `CACHE_PREFIX`, `CACHE_VERSION` – change the namespace alias used by the decorators. 【F:src/svc_infra/cache/README.md†L20-L173】
- `CACHE_TTL_DEFAULT`, `CACHE_TTL_SHORT`, `CACHE_TTL_LONG` – override canonical TTL buckets. 【F:src/svc_infra/cache/ttl.py†L26-L55】

## Easy integration: add_cache

Use the one-liner helper to wire cache initialization into your ASGI app lifecycle with sensible defaults. This doesn’t replace the decorators; it standardizes init/readiness/shutdown and exposes a handle for convenience.

```python
from fastapi import FastAPI
from svc_infra.cache import add_cache, cache_read, cache_write, resource

app = FastAPI()

# Wires startup (init + readiness) and shutdown (graceful close). Idempotent.
add_cache(app)

user = resource("user", "user_id")

@user.cache_read(suffix="profile", ttl=300)
async def get_user_profile(user_id: int):
    ...

@user.cache_write()
async def update_user_profile(user_id: int, payload):
    ...

# Optional: direct cache instance for advanced scenarios
# available after startup when using add_cache(app)
# app.state.cache -> cashews cache instance
```

### Env-driven defaults

- URL: `CACHE_URL` → `REDIS_URL` → `mem://`
- Prefix: `CACHE_PREFIX` (default `svc`)
- Version: `CACHE_VERSION` (default `v1`)

You can override explicitly:

```python
add_cache(app, url="redis://localhost:6379/0", prefix="myapp", version="v2")
```

### Behavior

- Idempotent: multiple calls won’t duplicate handlers.
- Startup/shutdown hooks: registered when supported by the app; startup performs a readiness probe. Startup is optional for correctness, but recommended for production reliability.
- app.state exposure: by default, exposes `app.state.cache` to access the underlying cashews instance.

### No-app usage

If you’re not wiring an app (e.g., a script), you can initialize without startup hooks:

```python
from svc_infra.cache import add_cache

shutdown = add_cache(None)  # immediate init (best-effort)
# ... do work ...
# call shutdown() is a no-op placeholder for symmetry
```
