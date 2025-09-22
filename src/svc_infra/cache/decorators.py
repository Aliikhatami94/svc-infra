"""
Cache decorators and utilities for read/write operations.

This module provides high-level decorators for caching read operations,
invalidating cache on write operations, and managing cache recaching strategies.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Awaitable, Callable, Iterable, Optional, Tuple, Union

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

from .ttl import validate_ttl
from .utils import normalize_cache_key, validate_cache_key

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

    def _build_key_template() -> str:
        """Convert key to template string."""
        if isinstance(key, tuple):
            parts = [part for part in key if part]
            return ":".join(part.strip(":") for part in parts)
        return str(key)

    def _create_tags_function(tags_param):
        """Create a tags function that handles various tag input types."""
        if tags_param is None:
            return lambda *_args, **_kwargs: []

        if callable(tags_param):

            def _callable_tags(*args, **kwargs):
                try:
                    result = tags_param(*args, **kwargs)
                    return list(result) if result is not None else []
                except Exception as e:
                    logger.warning(f"Tags function failed: {e}")
                    return []

            return _callable_tags

        # Static tags
        static_tags = list(tags_param)
        return lambda *_args, **_kwargs: static_tags

    def _build_key_variants_renderer(template: str) -> Callable[..., list[str]]:
        """
        Build a function that generates all possible cache key variants.

        This is used by cache writers to delete exact keys before recaching.
        """
        namespace = _alias() or ""

        def _get_variants(**kwargs) -> list[str]:
            try:
                rendered_key = template.format(**kwargs)
                rendered_key = validate_cache_key(rendered_key)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to render cache key template '{template}': {e}")
                return []

            variants = []

            # With namespace prefix
            if namespace and not rendered_key.startswith(f"{namespace}:"):
                with_namespace = f"{namespace}:{rendered_key}"
                variants.append(with_namespace)

            # Without namespace prefix (fallback)
            if not namespace or not rendered_key.startswith(f"{namespace}:"):
                variants.append(rendered_key)
            elif namespace and rendered_key.startswith(f"{namespace}:"):
                without_namespace = rendered_key[len(namespace) + 1 :]
                if without_namespace:
                    variants.append(without_namespace)

            # Remove duplicates while preserving order
            unique_variants = []
            for variant in variants:
                if variant and variant not in unique_variants:
                    unique_variants.append(variant)

            return unique_variants

        return _get_variants

    def _decorator(func: Callable[..., Awaitable[Any]]):
        template = _build_key_template()
        namespace = _alias() or ""
        tags_func = _create_tags_function(tags)

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
        setattr(wrapped, "__svc_key_variants__", _build_key_variants_renderer(template))

        return wrapped

    return _decorator


# Back-compatibility alias
cached = cache_read


# ---------- Recache Support ----------


@dataclass(frozen=True)
class RecachePlan:
    """
    Configuration for recaching operations after cache invalidation.

    Attributes:
        getter: The async function to call for recaching
        include: Parameter names to pass through from mutation
        rename: Mapping of mutation parameter names to getter parameter names
        extra: Additional fixed parameters for the getter
        key: Optional cache key template for deletion before warming
    """

    getter: Callable[..., Awaitable[Any]]
    include: Optional[Iterable[str]] = None
    rename: Optional[dict[str, str]] = None
    extra: Optional[dict[str, Any]] = None
    key: Optional[Union[str, tuple[str, ...]]] = None


def recache(
    getter: Callable[..., Awaitable[Any]],
    *,
    include: Optional[Iterable[str]] = None,
    rename: Optional[dict[str, str]] = None,
    extra: Optional[dict[str, Any]] = None,
    key: Optional[Union[str, tuple[str, ...]]] = None,
) -> RecachePlan:
    """
    Create a recache plan for cache warming after invalidation.

    Args:
        getter: Async function to call for recaching
        include: Parameter names to include from mutation
        rename: Parameter name mappings (mutation -> getter)
        extra: Additional fixed parameters
        key: Cache key template for precise deletion

    Returns:
        RecachePlan instance
    """
    return RecachePlan(getter=getter, include=include, rename=rename, extra=extra, key=key)


RecacheSpec = Union[
    Callable[..., Awaitable[Any]],
    RecachePlan,
    tuple[Callable[..., Awaitable[Any]], Any],  # Legacy format
]


# ---------- Tag Invalidation ----------


async def invalidate_tags(*tags: str) -> int:
    """
    Invalidate cache entries by tags with fallback strategies.

    This function tries multiple approaches to invalidate cache tags,
    providing compatibility across different cashews versions.

    Args:
        *tags: Cache tags to invalidate

    Returns:
        Number of invalidated entries (best effort)
    """
    if not tags:
        return 0

    count = 0

    # Strategy 1: Modern cashews invalidate with tags parameter
    try:
        result = await _cache.invalidate(tags=list(tags))
        return int(result) if isinstance(result, int) else len(tags)
    except (TypeError, AttributeError):
        pass
    except Exception as e:
        logger.warning(f"Modern tag invalidation failed: {e}")

    # Strategy 2: Legacy cashews invalidate with positional args
    try:
        result = await _cache.invalidate(*tags)
        return int(result) if isinstance(result, int) else len(tags)
    except (TypeError, AttributeError):
        pass
    except Exception as e:
        logger.warning(f"Legacy tag invalidation failed: {e}")

    # Strategy 3: Individual tag methods
    for tag in tags:
        for method_name in ("delete_tag", "invalidate_tag", "tag_invalidate"):
            if hasattr(_cache, method_name):
                try:
                    method = getattr(_cache, method_name)
                    result = await method(tag)
                    count += int(result) if isinstance(result, int) else 1
                    break
                except Exception as e:
                    logger.debug(f"Tag method {method_name} failed for tag {tag}: {e}")
                    continue
        else:
            # Strategy 4: Pattern matching fallback
            for method_name in ("delete_match", "invalidate_match", "invalidate"):
                if hasattr(_cache, method_name):
                    try:
                        method = getattr(_cache, method_name)
                        pattern = f"*{tag}*"
                        result = await method(pattern)
                        count += int(result) if isinstance(result, int) else 1
                        break
                    except Exception as e:
                        logger.debug(f"Pattern method {method_name} failed for tag {tag}: {e}")
                        continue

    return count


def _generate_key_variants(
    template: Union[str, tuple[str, ...]], params: dict[str, Any]
) -> list[str]:
    """
    Generate all possible cache key variants for deletion.

    Args:
        template: Key template (string or tuple)
        params: Template parameters

    Returns:
        List of possible cache key variants
    """
    try:
        normalized_key = normalize_cache_key(template, **params)
        validated_key = validate_cache_key(normalized_key)
    except (KeyError, ValueError) as e:
        logger.warning(f"Failed to generate key variants: {e}")
        return []

    namespace = _alias() or ""
    variants = []

    # Add namespaced version
    if namespace and not validated_key.startswith(f"{namespace}:"):
        variants.append(f"{namespace}:{validated_key}")

    # Add non-namespaced version
    if not namespace or not validated_key.startswith(f"{namespace}:"):
        variants.append(validated_key)
    elif namespace and validated_key.startswith(f"{namespace}:"):
        without_namespace = validated_key[len(namespace) + 1 :]
        if without_namespace:
            variants.append(without_namespace)

    # Remove duplicates while preserving order
    unique_variants = []
    for variant in variants:
        if variant and variant not in unique_variants:
            unique_variants.append(variant)

    return unique_variants


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

    def _resolve_tags(*args, **kwargs) -> list[str]:
        """Resolve tags from static list or callable."""
        try:
            if callable(tags):
                result = tags(*args, **kwargs)
                return list(result) if result is not None else []
            return list(tags)
        except Exception as e:
            logger.error(f"Failed to resolve cache tags: {e}")
            return []

    def _build_getter_kwargs(
        spec: RecacheSpec, mut_args: tuple, mut_kwargs: dict
    ) -> tuple[Callable, dict]:
        """Build keyword arguments for getter function from mutation parameters."""

        # Handle RecachePlan objects
        if isinstance(spec, RecachePlan):
            getter = spec.getter
            getter_params = signature(getter).parameters
            call_kwargs: dict[str, Any] = {}

            # Include specified parameters
            source_params = dict(mut_kwargs)
            if spec.include:
                include_set = set(spec.include)
                source_params = {k: v for k, v in source_params.items() if k in include_set}

            # Apply parameter renaming
            if spec.rename:
                for src_name, dst_name in spec.rename.items():
                    if src_name in mut_kwargs and dst_name in getter_params:
                        call_kwargs[dst_name] = mut_kwargs[src_name]

            # Add direct parameter matches
            for param_name in getter_params.keys():
                if param_name not in call_kwargs and param_name in source_params:
                    call_kwargs[param_name] = source_params[param_name]

            # Add extra parameters
            if spec.extra:
                for param_name, value in spec.extra.items():
                    if param_name in getter_params:
                        call_kwargs[param_name] = value

            # Filter to only include valid parameters
            call_kwargs = {k: v for k, v in call_kwargs.items() if k in getter_params}

            # Check for missing required parameters
            for param_name, param in getter_params.items():
                if param.default is Parameter.empty and param_name not in call_kwargs:
                    logger.debug(
                        f"Recache missing required parameter '{param_name}' for {getattr(getter, '__name__', getter)}"
                    )

            return getter, call_kwargs

        # Handle legacy tuple format
        if isinstance(spec, tuple):
            getter, mapping_or_builder = spec
            getter_params = signature(getter).parameters
            call_kwargs: dict[str, Any] = {}

            if callable(mapping_or_builder):
                try:
                    produced = mapping_or_builder(*mut_args, **mut_kwargs) or {}
                    if isinstance(produced, dict):
                        for param_name, value in produced.items():
                            if param_name in getter_params:
                                call_kwargs[param_name] = value
                except Exception as e:
                    logger.warning(f"Recache mapping function failed: {e}")
            elif isinstance(mapping_or_builder, dict):
                for getter_param, source in mapping_or_builder.items():
                    if getter_param not in getter_params:
                        continue
                    try:
                        if callable(source):
                            call_kwargs[getter_param] = source(*mut_args, **mut_kwargs)
                        elif isinstance(source, str) and source in mut_kwargs:
                            call_kwargs[getter_param] = mut_kwargs[source]
                    except Exception as e:
                        logger.warning(f"Recache parameter mapping failed for {getter_param}: {e}")

            # Add direct parameter matches
            for param_name in getter_params.keys():
                if param_name not in call_kwargs and param_name in mut_kwargs:
                    call_kwargs[param_name] = mut_kwargs[param_name]

            call_kwargs = {k: v for k, v in call_kwargs.items() if k in getter_params}
            return getter, call_kwargs

        # Handle simple getter function
        getter = spec
        getter_params = signature(getter).parameters
        call_kwargs = {k: v for k, v in mut_kwargs.items() if k in getter_params}
        return getter, call_kwargs

    async def _execute_recache(specs: Iterable[RecacheSpec], *mut_args, **mut_kwargs) -> None:
        """Execute recache operations with concurrency control."""
        if not specs:
            return

        semaphore = asyncio.Semaphore(recache_max_concurrency)

        async def _run_single_recache(spec: RecacheSpec) -> None:
            async with semaphore:
                try:
                    getter, call_kwargs = _build_getter_kwargs(spec, mut_args, mut_kwargs)

                    # Delete specific cache keys if RecachePlan has key template
                    if isinstance(spec, RecachePlan) and spec.key is not None:
                        key_variants = _generate_key_variants(spec.key, call_kwargs)
                        for key_variant in key_variants:
                            try:
                                await _cache.delete(key_variant)
                            except Exception as e:
                                logger.debug(f"Failed to delete cache key {key_variant}: {e}")

                    # Execute the getter to warm the cache
                    await getter(**call_kwargs)

                except Exception as e:
                    logger.error(f"Recache operation failed: {e}")

        # Execute all recache operations concurrently
        await asyncio.gather(*[_run_single_recache(spec) for spec in specs], return_exceptions=True)

    def _decorator(func: Callable[..., Awaitable[Any]]):
        async def _wrapped(*args, **kwargs):
            # Execute the original function
            result = await func(*args, **kwargs)

            try:
                # Invalidate cache tags
                resolved_tags = _resolve_tags(*args, **kwargs)
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
                        await _execute_recache(recache, *args, **kwargs)
                    except Exception as e:
                        logger.error(f"Cache recaching failed: {e}")

            return result

        return _wrapped

    return _decorator


# Back-compatibility alias
mutates = cache_write


# ---------- Resource Management ----------


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
