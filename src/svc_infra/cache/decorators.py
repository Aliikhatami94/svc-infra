"""
Cache decorators and utilities for read/write operations.

This module provides high-level decorators for caching read operations,
invalidating cache on write operations, and managing cache recaching strategies.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

from .keys import (
    build_key_template,
    build_key_variants_renderer,
    create_tags_function,
    resolve_tags,
)
from .recache import RecachePlan, RecacheSpec, execute_recache, recache
from .resources import Resource, entity, resource
from .tags import invalidate_tags
from .ttl import validate_ttl

logger = logging.getLogger(__name__)


# ---------- Cache Initialization ----------


def init_cache(
    *, url: str | None = None, prefix: str | None = None, version: str | None = None
) -> None:
    """
    Initialize cache synchronously.

    Args:
        url: Cache backend URL
        prefix: Cache key prefix
        version: Cache version
    """
    _setup_cache(url=url, prefix=prefix, version=version)


async def init_cache_async(
    *, url: str | None = None, prefix: str | None = None, version: str | None = None
) -> None:
    """
    Initialize cache asynchronously and wait for readiness.

    Args:
        url: Cache backend URL
        prefix: Cache key prefix
        version: Cache version
    """
    _setup_cache(url=url, prefix=prefix, version=version)
    await _wait_ready()


# ---------- Cache Read Operations ----------


def cache_read(
    *,
    key: Union[str, tuple[str, ...]],
    ttl: Optional[int] = None,
    tags: Optional[Union[Iterable[str], Callable[..., Iterable[str]]]] = None,
    early_ttl: Optional[int] = None,
    refresh: Optional[bool] = None,
):
    """
    Cache decorator for read operations with version-resilient key handling.

    This decorator wraps functions to cache their results using the cashews library.
    It handles tuple keys by converting them to template strings and applies
    namespace prefixes automatically.

    Args:
        key: Cache key template (string or tuple of strings)
        ttl: Time to live in seconds (defaults to TTL_DEFAULT)
        tags: Cache tags for invalidation (static list or callable)
        early_ttl: Early expiration time for cache warming
        refresh: Whether to refresh cache on access

    Returns:
        Decorated function with caching capabilities

    Example:
        @cache_read(key="user:{user_id}:profile", ttl=300)
        async def get_user_profile(user_id: int):
            return await fetch_profile(user_id)
    """
    ttl_val = validate_ttl(ttl)
    template = build_key_template(key)
    namespace = _alias() or ""
    # Build a tags function that renders any templates against the call kwargs
    base_tags_func = create_tags_function(tags)

    def tags_func(*_args, **call_kwargs):
        try:
            raw = base_tags_func(*_args, **call_kwargs) or []
            rendered = []
            for t in raw:
                if isinstance(t, str) and ("{" in t and "}" in t):
                    try:
                        rendered.append(t.format(**call_kwargs))
                    except Exception:
                        # Best effort: fall back to original
                        rendered.append(t)
                else:
                    rendered.append(t)
            return rendered
        except Exception:
            return raw if isinstance(raw, list) else []

    def _decorator(func: Callable[..., Awaitable[Any]]):
        # Try different cashews cache decorator signatures for compatibility
        cache_kwargs = {"tags": tags_func}
        if early_ttl is not None:
            cache_kwargs["early_ttl"] = early_ttl
        if refresh is not None:
            cache_kwargs["refresh"] = refresh

        wrapped = None
        error_msgs = []

        # Attempt 1: With prefix parameter (preferred)
        if namespace:
            try:
                wrapped = _cache.cache(ttl_val, template, prefix=namespace, **cache_kwargs)(func)
            except TypeError as e:
                error_msgs.append(f"prefix parameter: {e}")

        # Attempt 2: With embedded namespace in key
        if wrapped is None:
            try:
                key_with_namespace = (
                    f"{namespace}:{template}"
                    if namespace and not template.startswith(f"{namespace}:")
                    else template
                )
                wrapped = _cache.cache(ttl_val, key_with_namespace, **cache_kwargs)(func)
            except TypeError as e:
                error_msgs.append(f"embedded namespace: {e}")

        # Attempt 3: Minimal fallback
        if wrapped is None:
            try:
                key_with_namespace = f"{namespace}:{template}" if namespace else template
                wrapped = _cache.cache(ttl_val, key_with_namespace)(func)
            except Exception as e:
                error_msgs.append(f"minimal fallback: {e}")
                logger.error(f"All cache decorator attempts failed: {error_msgs}")
                raise RuntimeError(f"Failed to apply cache decorator: {error_msgs[-1]}") from e

        # Attach key variants renderer for cache writers
        setattr(wrapped, "__svc_key_variants__", build_key_variants_renderer(template))
        return wrapped

    return _decorator


# Back-compatibility alias
cached = cache_read


# ---------- Cache Write Operations ----------


def cache_write(
    *,
    tags: Union[Iterable[str], Callable[..., Iterable[str]]],
    recache: Optional[Iterable[RecacheSpec]] = None,
    recache_max_concurrency: int = 5,
):
    """
    Cache invalidation decorator for write operations.

    This decorator invalidates cache tags after write operations and
    optionally recaches dependent data to warm the cache.

    Args:
        tags: Cache tags to invalidate (static list or callable)
        recache: Specifications for recaching operations
        recache_max_concurrency: Maximum concurrent recache operations

    Returns:
        Decorated function with cache invalidation

    Example:
        @cache_write(
            tags=["user:{user_id}"],
            recache=[recache(get_user_profile, include=["user_id"])]
        )
        async def update_user(user_id: int, data: dict):
            return await save_user(user_id, data)
    """

    def _decorator(func: Callable[..., Awaitable[Any]]):
        async def _wrapped(*args, **kwargs):
            # Execute the original function
            result = await func(*args, **kwargs)

            try:
                # Invalidate cache tags
                resolved_tags = resolve_tags(tags, *args, **kwargs)
                if resolved_tags:
                    invalidated_count = await invalidate_tags(*resolved_tags)
                    logger.debug(
                        f"Invalidated {invalidated_count} cache entries for tags: {resolved_tags}"
                    )
            except Exception as e:
                logger.error(f"Cache tag invalidation failed: {e}")
            finally:
                # Execute recache operations (always run, even if invalidation fails)
                if recache:
                    try:
                        await execute_recache(
                            recache, *args, max_concurrency=recache_max_concurrency, **kwargs
                        )
                    except Exception as e:
                        logger.error(f"Cache recaching failed: {e}")

            return result

        return _wrapped

    return _decorator


# Back-compatibility alias
mutates = cache_write


# ---------- Re-exports for backward compatibility ----------

# Export all the classes and functions that were previously in this file
__all__ = [
    # Core decorators
    "cache_read",
    "cached",
    "cache_write",
    "mutates",
    # Initialization
    "init_cache",
    "init_cache_async",
    # Recaching
    "RecachePlan",
    "RecacheSpec",
    "recache",
    # Tag invalidation
    "invalidate_tags",
    # Resource management
    "Resource",
    "resource",
    "entity",
]
