from __future__ import annotations

from typing import Any, Protocol


class CacheBackend(Protocol):
    pass


#     async def get(self, key: str) -> Any: ...
#     async def set(self, key: str, value: Any, ttl: int | None = None) -> bool: ...
#     async def delete(self, *keys: str) -> int: ...
#     async def mget(self, *keys: str) -> list[Any | None]: ...
#     async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int: ...


class CacheService:
    """Thin orchestration layer (shared for all backends)."""

    def __init__(self, backend: CacheBackend, *, prefix: str, default_ttl: int):
        self.backend = backend
        self.prefix = prefix.rstrip(":")
        self.default_ttl = default_ttl

    def key(self, *parts: str | int) -> str:
        from .key import namespaced

        return namespaced(self.prefix, *parts)

    async def get_json(self, key: str):
        from .codec import loads

        raw = await self.backend.get(key)
        return loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int | None = None):
        from .codec import dumps

        return await self.backend.set(key, dumps(value), ttl or self.default_ttl)

    async def drop(self, *keys: str) -> int:
        return await self.backend.delete(*keys)
