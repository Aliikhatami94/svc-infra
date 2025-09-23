"""
Resource-based cache management utilities.

This module provides convenient decorators for entity-based caching
with standardized key patterns and tag management.
"""

import asyncio
import inspect
import logging
from typing import Callable, Optional, Tuple

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias

logger = logging.getLogger(__name__)


class Resource:
    """
    Resource-based cache management helper.

    This class provides convenient decorators for entity-based caching
    with standardized key patterns and tag management.
    """

    def __init__(self, name: str, id_field: str):
        """
        Initialize resource cache manager.

        Args:
            name: Resource name (e.g., "user", "product")
            id_field: ID field name (e.g., "user_id", "product_id")
        """
        self.name = name
        self.id_field = id_field

    def cache_read(
        self,
        *,
        suffix: str,
        ttl: int,
        key_template: Optional[str] = None,
        tags_template: Optional[Tuple[str, ...]] = None,
        lock: bool = True,
    ):
        """
        Cache decorator for resource read operations.

        Args:
            suffix: Cache key suffix (e.g., "profile", "settings")
            ttl: Time to live in seconds
            key_template: Custom key template (defaults to "{name}:{suffix}:{id_field}")
            tags_template: Custom tags template (defaults to ("{name}:{id_field}",))
            lock: Enable singleflight to prevent cache stampede

        Returns:
            Cache decorator function
        """
        key_template = key_template or f"{self.name}:{suffix}:{{{self.id_field}}}"
        tags_template = tags_template or (f"{self.name}:{{{self.id_field}}}",)

        def _decorator(func: Callable):
            try:
                return _cache(ttl=ttl, key=key_template, tags=tags_template, lock=lock)(func)
            except TypeError:
                # Fallback for older cashews versions
                return _cache(ttl=ttl, key=key_template, tags=tags_template)(func)

        return _decorator

    def cache_write(
        self,
        *,
        recache: Optional[list[tuple[Callable, Callable]]] = None,
        recache_max_concurrency: int = 5,
    ):
        """
        Cache invalidation decorator for resource write operations.

        Args:
            recache: List of (getter, kwargs_builder) pairs for recaching
            recache_max_concurrency: Maximum concurrent recache operations

        Returns:
            Cache invalidation decorator
        """

        async def _maybe_await(value):
            """Await value if it's awaitable, otherwise return as-is."""
            if inspect.isawaitable(value):
                return await value
            return value

        async def _delete_entity_keys(entity_name: str, entity_id: str) -> None:
            """Delete all cache keys for a specific entity."""
            namespace = _alias() or ""
            namespace_prefix = (
                f"{namespace}:" if namespace and not namespace.endswith(":") else namespace
            )

            # Generate candidate keys to delete
            key_patterns = [
                f"{entity_name}:profile:{entity_id}",
                f"{entity_name}:profile_view:{entity_id}",
                f"{entity_name}:settings:{entity_id}",
                f"{entity_name}:*:{entity_id}",
            ]

            candidates = []
            for pattern in key_patterns:
                # Add namespaced versions
                if namespace_prefix:
                    candidates.append(f"{namespace_prefix}{pattern}")
                # Add non-namespaced versions
                candidates.append(pattern)

            # Try precise deletions first
            for key in candidates:
                if "*" not in key:  # Skip wildcard patterns for precise deletion
                    try:
                        deleter = getattr(_cache, "delete", None)
                        if callable(deleter):
                            await _maybe_await(deleter(key))
                    except Exception as e:
                        logger.debug(f"Failed to delete cache key {key}: {e}")

            # Wildcard deletions as safety net
            delete_match = getattr(_cache, "delete_match", None)
            if callable(delete_match):
                try:
                    # Namespaced wildcard
                    if namespace_prefix:
                        await _maybe_await(
                            delete_match(f"{namespace_prefix}{entity_name}:*:{entity_id}*")
                        )
                    # Non-namespaced wildcard
                    await _maybe_await(delete_match(f"{entity_name}:*:{entity_id}*"))
                except Exception as e:
                    logger.debug(f"Wildcard deletion failed: {e}")

        async def _execute_resource_recache(specs, *mut_args, **mut_kwargs) -> None:
            """Execute recache operations for resource."""
            if not specs:
                return

            semaphore = asyncio.Semaphore(recache_max_concurrency)

            async def _run_single_resource_recache(spec):
                getter, kwargs_builder = spec
                try:
                    call_kwargs = kwargs_builder(*mut_args, **mut_kwargs) or {}
                    async with semaphore:
                        await _maybe_await(getter(**call_kwargs))
                except Exception as e:
                    logger.error(f"Resource recache failed: {e}")

            await asyncio.gather(
                *[_run_single_resource_recache(spec) for spec in specs], return_exceptions=True
            )

        def _decorator(mutator: Callable):
            async def _wrapped(*args, **kwargs):
                # Execute the mutation
                result = await _maybe_await(mutator(*args, **kwargs))

                entity_id = kwargs.get(self.id_field)
                if entity_id is not None:
                    try:
                        # Tag invalidation
                        invalidate_func = getattr(_cache, "invalidate", None)
                        if callable(invalidate_func):
                            await _maybe_await(invalidate_func(f"{self.name}:{entity_id}"))

                        # Precise key deletion
                        await _delete_entity_keys(self.name, str(entity_id))
                    except Exception as e:
                        logger.error(f"Resource cache invalidation failed: {e}")

                    # Recache operations
                    if recache:
                        try:
                            await _execute_resource_recache(recache, *args, **kwargs)
                        except Exception as e:
                            logger.error(f"Resource recaching failed: {e}")

                return result

            return _wrapped

        return _decorator


def resource(name: str, id_field: str) -> Resource:
    """
    Create a resource cache manager.

    Args:
        name: Resource name
        id_field: ID field name

    Returns:
        Resource instance for cache management
    """
    return Resource(name, id_field)


# Legacy alias for backward compatibility
def entity(name: str, id_param: str) -> Resource:
    """Legacy alias for resource() function."""
    return Resource(name, id_param)
