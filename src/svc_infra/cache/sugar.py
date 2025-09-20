from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable, Iterable

from cashews import cache as _cache


def _hash_args(*args, **kwargs) -> str:
    try:
        raw = json.dumps([args, kwargs], default=str, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = repr((args, kwargs))
    return hashlib.sha1(raw.encode()).hexdigest()


def cached(
    prefix: str,
    ttl: int | str | None = None,
    *,
    tags: Callable[..., Iterable[str]] | Iterable[str] | None = None,
):
    """
    Cache async function results. Keys are stable by function args (hashed).
    - prefix: logical namespace ("user", "list:orders", etc.)
    - ttl: seconds or cashews duration string ("5m", "1h")
    - tags: iterable or callable -> list[str] for tag-based invalidation
    """

    def wrap(fn: Callable[..., Awaitable[Any]]):
        # cashews can build keys from templated kwargs; here we just provide a simple hashed suffix
        async def _key_builder(*a, **kw) -> str:
            return f"{prefix}:{_hash_args(*a, **kw)}"

        if callable(tags):

            async def _tags_builder(*a, **kw):
                vals = tags(*a, **kw)
                return list(vals) if vals else []

        elif isinstance(tags, (list, tuple, set)):
            const_tags = list(tags)

            async def _tags_builder(*a, **kw):
                return const_tags

        else:
            _tags_builder = None

        decorator = _cache.cache(
            key_builder=_key_builder,
            ttl=ttl,
            tags=_tags_builder,  # cashews accepts a callable for dynamic tags
        )

        return decorator(fn)

    return wrap


async def invalidate_tags(*tags: str) -> int:
    """
    Remove all cache entries bound to any of the provided tags.
    Returns number of keys invalidated (best-effort).
    """
    if not tags:
        return 0
    # cashews invalidates by tags efficiently
    return await _cache.invalidate(tags=list(tags))
