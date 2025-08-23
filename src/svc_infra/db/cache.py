from __future__ import annotations

from typing import Any, Optional, Protocol


class BaseCache(Protocol):
    async def get(self, key: str) -> Optional[Any]:
        ...

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...


class NullCache:
    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None


class InMemoryCache:
    """Simple in-memory async cache for tests/dev only."""

    def __init__(self, namespace: str = ""):
        self._store: dict[str, Any] = {}
        self._ns = (namespace + ":") if namespace else ""

    def _k(self, key: str) -> str:
        return self._ns + key

    async def get(self, key: str) -> Optional[Any]:
        return self._store.get(self._k(key))

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:  # ttl ignored
        self._store[self._k(key)] = value

    async def delete(self, key: str) -> None:
        self._store.pop(self._k(key), None)
