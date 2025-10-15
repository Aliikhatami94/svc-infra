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
