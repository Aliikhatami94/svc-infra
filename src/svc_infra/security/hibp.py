from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional

from svc_infra.http import new_httpx_client


def sha1_hex(data: str) -> str:
    return hashlib.sha1(data.encode("utf-8")).hexdigest().upper()


@dataclass
class CacheEntry:
    body: str
    expires_at: float


class HIBPClient:
    """Minimal HaveIBeenPwned range API client with simple in-memory cache.

    - Uses k-anonymity range query: send first 5 chars of SHA1 hash, receive suffix list.
    - Caches prefix responses for TTL to avoid repeated network calls.
    - Synchronous implementation to allow use in sync validators.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.pwnedpasswords.com",
        ttl_seconds: int = 3600,
        timeout: float = 5.0,
        user_agent: str = "svc-infra/hibp",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        self.user_agent = user_agent
        self._cache: Dict[str, CacheEntry] = {}
        # Use central factory for consistent defaults; retain explicit timeout override
        self._http = new_httpx_client(
            timeout_seconds=self.timeout,
            headers={"User-Agent": self.user_agent},
        )

    def _get_cached(self, prefix: str) -> Optional[str]:
        now = time.time()
        ent = self._cache.get(prefix)
        if ent and ent.expires_at > now:
            return ent.body
        return None

    def _set_cache(self, prefix: str, body: str) -> None:
        self._cache[prefix] = CacheEntry(body=body, expires_at=time.time() + self.ttl_seconds)

    def range_query(self, prefix: str) -> str:
        cached = self._get_cached(prefix)
        if cached is not None:
            return cached
        url = f"{self.base_url}/range/{prefix}"
        resp = self._http.get(url)
        resp.raise_for_status()
        body = resp.text
        self._set_cache(prefix, body)
        return body

    def is_breached(self, password: str) -> bool:
        full = sha1_hex(password)
        prefix, suffix = full[:5], full[5:]
        try:
            body = self.range_query(prefix)
        except Exception:
            # Fail-open: if HIBP unavailable, do not block users.
            return False

        for line in body.splitlines():
            # Lines formatted as "SUFFIX:COUNT"
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 2:
                continue
            sfx = parts[0].strip().upper()
            if sfx == suffix:
                # Count > 0 implies breached
                try:
                    return int(parts[1].strip()) > 0
                except ValueError:
                    return True
        return False


__all__ = ["HIBPClient", "sha1_hex"]
