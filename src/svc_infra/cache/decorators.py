"""
Cache decorators and utilities for read/write operations.

This module provides high-level decorators for caching read operations,
invalidating cache on write operations, and managing cache recaching strategies.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

from .keys import build_key_template, build_key_variants_renderer, resolve_tags
from .recache import RecachePlan, RecacheSpec, execute_recache, recache
from .resources import Resource, entity, resource
from .tags import invalidate_tags
from .ttl import validate_ttl
from .utils import validate_cache_key

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
    key: str | tuple[str, ...],
    ttl: int | None = None,
    tags: Iterable[str] | Callable[..., Iterable[str]] | None = None,
    early_ttl: int | None = None,
    refresh: bool | None = None,
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
    # Cashews expects `tags` to be an iterable of (template) strings.
    # If no explicit tags are provided, default to tagging by the key template.
    # This enables the common pattern:
    #   @cache_read(key="thing:{id}")
    #   @cache_write(tags=["thing:{id}"])
    # where writes invalidate reads without requiring tags on every read.
    dynamic_tags_func: Callable[..., Iterable[str]] | None = None
    if tags is None:
        tags_param: Iterable[str] = (template,)
    elif callable(tags):
        # Preserve API surface area, but cashews doesn't accept callables here.
        # We'll attach tag mappings manually after each call.
        dynamic_tags_func = tags
        tags_param = ()
    else:
        tags_param = tags

    def _decorator(func: Callable[..., Awaitable[Any]]):
        # Try different cashews cache decorator signatures for compatibility
        cache_kwargs: dict[str, Any] = {"tags": tuple(tags_param)}
        if early_ttl is not None:
            cache_kwargs["early_ttl"] = early_ttl
        if refresh is not None:
            cache_kwargs["refresh"] = refresh

        wrapped = None
        error_msgs: list[str] = []

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
        wrapped.__svc_key_variants__ = build_key_variants_renderer(template)  # type: ignore[attr-defined]

        # If tags were provided as a callable, populate cashews tag sets manually.
        # This is best-effort and only affects invalidation-by-tag behavior.
        if dynamic_tags_func is None:
            return wrapped

        sig = inspect.signature(func)
        tag_key_prefix = getattr(_cache, "_tags_key_prefix", "_tag:")

        async def _wrapped_with_dynamic_tags(*args, **kwargs):
            result = await wrapped(*args, **kwargs)

            try:
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                ctx = dict(bound.arguments)

                rendered_key = validate_cache_key(template.format(**ctx))
                full_key = f"{namespace}:{rendered_key}" if namespace else rendered_key

                raw_tags = dynamic_tags_func(*args, **kwargs)
                for t in list(raw_tags) if raw_tags is not None else []:
                    tag_val = str(t)
                    if "{" in tag_val and "}" in tag_val:
                        try:
                            tag_val = tag_val.format(**ctx)
                        except Exception:
                            pass
                    if tag_val:
                        await _cache.set_add(tag_key_prefix + tag_val, full_key, expire=ttl_val)
            except Exception:
                # Don't let best-effort tag mapping break cache reads.
                pass

            return result

        _wrapped_with_dynamic_tags.__svc_key_variants__ = getattr(  # type: ignore[attr-defined]
            wrapped, "__svc_key_variants__", None
        )
        return _wrapped_with_dynamic_tags

    return _decorator


# Back-compatibility alias
cached = cache_read


# ---------- Cache Write Operations ----------


def cache_write(
    *,
    tags: Iterable[str] | Callable[..., Iterable[str]],
    recache: Iterable[RecacheSpec] | None = None,
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
                            recache,
                            *args,
                            max_concurrency=recache_max_concurrency,
                            **kwargs,
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
