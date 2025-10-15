from __future__ import annotations

import time
from typing import Protocol


class InboxStore(Protocol):
    def mark_if_new(self, key: str, ttl_seconds: int = 24 * 3600) -> bool:
        """Mark key as processed if not seen; return True if newly marked, False if duplicate."""
        ...

    def purge_expired(self) -> int:
        """Optional: remove expired keys, return number purged."""
        ...

    def is_marked(self, key: str) -> bool:
        """Return True if key is already marked (not expired), without modifying it."""
        ...


class InMemoryInboxStore:
    def __init__(self) -> None:
        self._keys: dict[str, float] = {}

    def mark_if_new(self, key: str, ttl_seconds: int = 24 * 3600) -> bool:
        now = time.time()
        exp = self._keys.get(key)
        if exp and exp > now:
            return False
        self._keys[key] = now + ttl_seconds
        return True

    def purge_expired(self) -> int:
        now = time.time()
        to_del = [k for k, e in self._keys.items() if e <= now]
        for k in to_del:
            self._keys.pop(k, None)
        return len(to_del)

    def is_marked(self, key: str) -> bool:
        now = time.time()
        exp = self._keys.get(key)
        return bool(exp and exp > now)


class SqlInboxStore:
    """Skeleton for a SQL-backed inbox store (dedupe table).

    Implementations should:
    - INSERT key with expires_at if not exists (unique constraint)
    - Return False on duplicate key violations
    - Periodically DELETE expired rows
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def mark_if_new(
        self, key: str, ttl_seconds: int = 24 * 3600
    ) -> bool:  # pragma: no cover - skeleton
        raise NotImplementedError

    def purge_expired(self) -> int:  # pragma: no cover - skeleton
        raise NotImplementedError

    def is_marked(self, key: str) -> bool:  # pragma: no cover - skeleton
        raise NotImplementedError
