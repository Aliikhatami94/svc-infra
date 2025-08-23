from __future__ import annotations

from typing import Any, Optional, Protocol


class BaseCache(Protocol):
    async def get(self, key: str) -> Optional[Any]:
        ...

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        ...


class NullCache:
    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        return None

