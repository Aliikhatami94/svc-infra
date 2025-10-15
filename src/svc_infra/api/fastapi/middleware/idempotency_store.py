from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Dict, Optional, Protocol


@dataclass
class IdempotencyEntry:
    req_hash: str
    exp: float
    # Optional response fields when available
    status: Optional[int] = None
    body_b64: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    media_type: Optional[str] = None


class IdempotencyStore(Protocol):
    def get(self, key: str) -> Optional[IdempotencyEntry]:
        pass

    def set_initial(self, key: str, req_hash: str, exp: float) -> bool:
        """Atomically create an entry if absent. Returns True if created, False if already exists."""
        pass

    def set_response(
        self,
        key: str,
        *,
        status: int,
        body: bytes,
        headers: Dict[str, str],
        media_type: Optional[str],
    ) -> None:
        pass

    def delete(self, key: str) -> None:
        pass


class InMemoryIdempotencyStore:
    def __init__(self):
        self._store: dict[str, IdempotencyEntry] = {}

    def get(self, key: str) -> Optional[IdempotencyEntry]:
        entry = self._store.get(key)
        if not entry:
            return None
        # expire lazily
        if entry.exp <= time.time():
            self._store.pop(key, None)
            return None
        return entry

    def set_initial(self, key: str, req_hash: str, exp: float) -> bool:
        now = time.time()
        existing = self._store.get(key)
        if existing and existing.exp > now:
            return False
        self._store[key] = IdempotencyEntry(req_hash=req_hash, exp=exp)
        return True

    def set_response(
        self,
        key: str,
        *,
        status: int,
        body: bytes,
        headers: Dict[str, str],
        media_type: Optional[str],
    ) -> None:
        entry = self._store.get(key)
        if not entry:
            # Create if missing to ensure replay works until exp
            entry = IdempotencyEntry(req_hash="", exp=time.time() + 60)
            self._store[key] = entry
        entry.status = status
        entry.body_b64 = base64.b64encode(body).decode()
        entry.headers = dict(headers)
        entry.media_type = media_type

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class RedisIdempotencyStore:
    """A simple Redis-backed store.

    Notes:
        - Uses GET/SET with JSON payload; initial claim uses SETNX semantics.
        - Not fully atomic for response update; sufficient for basic dedupe.
        - For strict guarantees, replace with a Lua script (future improvement).
    """

    def __init__(self, redis_client, *, prefix: str = "idmp"):
        self.r = redis_client
        self.prefix = prefix

    def _k(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Optional[IdempotencyEntry]:
        raw = self.r.get(self._k(key))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        entry = IdempotencyEntry(
            req_hash=data.get("req_hash", ""),
            exp=float(data.get("exp", 0)),
            status=data.get("status"),
            body_b64=data.get("body_b64"),
            headers=data.get("headers"),
            media_type=data.get("media_type"),
        )
        if entry.exp <= time.time():
            try:
                self.r.delete(self._k(key))
            except Exception:
                pass
            return None
        return entry

    def set_initial(self, key: str, req_hash: str, exp: float) -> bool:
        payload = json.dumps({"req_hash": req_hash, "exp": exp})
        # Attempt NX set
        ok = self.r.set(self._k(key), payload, nx=True)
        # If set, also set TTL (expire at exp)
        if ok:
            ttl = max(1, int(exp - time.time()))
            try:
                self.r.expire(self._k(key), ttl)
            except Exception:
                pass
            return True
        # If exists but expired, overwrite
        entry = self.get(key)
        if not entry:
            self.r.set(self._k(key), payload)
            ttl = max(1, int(exp - time.time()))
            try:
                self.r.expire(self._k(key), ttl)
            except Exception:
                pass
            return True
        return False

    def set_response(
        self,
        key: str,
        *,
        status: int,
        body: bytes,
        headers: Dict[str, str],
        media_type: Optional[str],
    ) -> None:
        entry = self.get(key)
        if not entry:
            # default short ttl if missing; caller should have set initial
            entry = IdempotencyEntry(req_hash="", exp=time.time() + 60)
        entry.status = status
        entry.body_b64 = base64.b64encode(body).decode()
        entry.headers = dict(headers)
        entry.media_type = media_type
        ttl = max(1, int(entry.exp - time.time()))
        payload = json.dumps(
            {
                "req_hash": entry.req_hash,
                "exp": entry.exp,
                "status": entry.status,
                "body_b64": entry.body_b64,
                "headers": entry.headers,
                "media_type": entry.media_type,
            }
        )
        self.r.set(self._k(key), payload, ex=ttl)

    def delete(self, key: str) -> None:
        try:
            self.r.delete(self._k(key))
        except Exception:
            pass
