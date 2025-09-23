"""
Cache decorators and utilities for read/write operations.

This module provides high-level decorators for caching read operations,
invalidating cache on write operations, and managing cache recaching strategies.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

from .ttl import validate_ttl
from .utils import normalize_cache_key, validate_cache_key

logger = logging.getLogger(__name__)

# Context variable for tracking if the original function was executed (cache miss)
_function_executed: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "function_executed", default=False
)

# Production readiness features - runtime toggleable
_DEBUG_MODE = False
_METRICS_ENABLED = False

# group name -> list of {"getter": <callable>, "key_template": str}
_read_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)


# Initialize from environment on first import
def _init_runtime_flags():
    global _DEBUG_MODE, _METRICS_ENABLED
    _DEBUG_MODE = os.getenv("CACHE_DEBUG", "").lower() in ("1", "true", "yes")
    _METRICS_ENABLED = os.getenv("CACHE_METRICS", "").lower() in ("1", "true", "yes")


# Initialize on import
_init_runtime_flags()


# Runtime toggles for post-import configuration
def enable_cache_debug(enabled: bool = True):
    """Enable or disable cache debug logging at runtime."""
    global _DEBUG_MODE
    _DEBUG_MODE = enabled


def enable_cache_metrics(enabled: bool = True):
    """Enable or disable cache metrics collection at runtime."""
    global _METRICS_ENABLED
    _METRICS_ENABLED = enabled


# Metrics counters (simple dict for now, can be replaced with OpenTelemetry)
_metrics = {
    "cache.hit": 0,
    "cache.miss": 0,
    "cache.invalidate.count": 0,
    "cache.warm.ms": 0,
    "cache.error": 0,
}


def _log_cache_operation(operation: str, key: str, **extra):
    """Log cache operations with debug info when debug mode is enabled."""
    if _DEBUG_MODE:
        logger.debug(f"[{operation}] key={key} {' '.join(f'{k}={v}' for k, v in extra.items())}")


def _increment_metric(metric_name: str, value: int = 1):
    """Increment a metric counter."""
    if _METRICS_ENABLED:
        _metrics[metric_name] = _metrics.get(metric_name, 0) + value


def get_metrics() -> dict[str, Any]:
    """Get current cache metrics."""
    return dict(_metrics)


def reset_metrics():
    """Reset all cache metrics."""
    global _metrics
    _metrics = {k: 0 for k in _metrics}


def _enforce_keyword_only_id(func: Callable, id_field: str):
    """
    Validate that the ID field is keyword-only for cache stability.
    Issues a warning in development if not properly structured.
    """
    sig = signature(func)
    if id_field in sig.parameters:
        param = sig.parameters[id_field]
        if param.kind != Parameter.KEYWORD_ONLY:
            warnings.warn(
                f"Function {func.__name__} should use keyword-only parameter "
                f"'*, {id_field}: ...' for cache key stability. "
                f"Current: {param.kind.name}",
                UserWarning,
                stacklevel=3,
            )


def _validate_tags_usage(tags, func_name: str):
    """
    Validate proper tags usage to prevent silent failures.
    """
    if isinstance(tags, (list, tuple)) and tags:
        # Check for literal string templates that should be lambdas
        for tag in tags:
            if isinstance(tag, str) and "{" in tag and "}" in tag:
                warnings.warn(
                    f"Function {func_name} uses literal tag template '{tag}'. "
                    f"Use a lambda instead: tags=lambda *, user_id, **__: [f'user:{{user_id}}']",
                    UserWarning,
                    stacklevel=4,
                )


# ---------- Negative Caching Support ----------


def negative_cache(*, ttl: int = 60, value: Any = None):
    """
    Helper for caching negative results (404s, missing entities) with short TTL.

    Args:
        ttl: Short TTL for negative results (default 60 seconds)
        value: Value to cache for missing items (default None)

    Returns:
        Value to be cached
    """
    return {"__negative__": True, "value": value, "cached_at": time.time()}


def is_negative_cache_result(result: Any) -> bool:
    """Check if a result is a negative cache entry."""
    return isinstance(result, dict) and result.get("__negative__") is True and "cached_at" in result


def unwrap_negative_cache_result(result: Any) -> Any:
    """Unwrap a negative cache result to get the original value."""
    if is_negative_cache_result(result):
        return result.get("value")
    return result


# ---------- Smooth Expiry Support ----------


def _calculate_smooth_expiry(ttl: int, jitter_ratio: float = 0.1) -> tuple[int, int]:
    """
    Calculate TTL and early_ttl for smooth expiry with jitter.

    Args:
        ttl: Base TTL in seconds
        jitter_ratio: Ratio of TTL to use for jitter (0.1 = 10%)

    Returns:
        Tuple of (ttl, early_ttl)
    """
    import random

    jitter = int(ttl * jitter_ratio)
    early_ttl = max(1, ttl - random.randint(0, jitter))
    return ttl, early_ttl


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

    # Log initialization status
    namespace = _alias() or "default"
    debug_status = "on" if _DEBUG_MODE else "off"
    metrics_status = "on" if _METRICS_ENABLED else "off"
    logger.info(f"Cache initialized: ns={namespace} debug={debug_status} metrics={metrics_status}")


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
    smooth_expiry: bool = False,
    group: Optional[str] = None,
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
        smooth_expiry: Enable automatic jitter to prevent synchronized expirations

    Returns:
        Decorated function with caching capabilities

    Example:
        @cache_read(key="user:{user_id}:profile", ttl=300)
        async def get_user_profile(*, user_id: int):
            return await fetch_profile(user_id)
    """
    ttl_val = validate_ttl(ttl)

    # Apply smooth expiry if requested
    if smooth_expiry and early_ttl is None:
        ttl_val, early_ttl = _calculate_smooth_expiry(ttl_val)

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
                    _increment_metric("cache.error")
                    return []

            return _callable_tags

        # Static tags - validate for common mistakes
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

        # Validate tags usage for common mistakes
        _validate_tags_usage(tags, func.__name__)

        # Create a wrapper that tracks function execution for accurate hit/miss detection
        async def _tracked_func(*args, **kwargs):
            # Set the context variable to indicate the function was executed (cache miss)
            _function_executed.set(True)
            return await func(*args, **kwargs)

        # Create instrumented wrapper for observability
        async def _instrumented_wrapper(*args, **kwargs):
            start_time = time.time()
            key_for_logging = template.format(**kwargs) if kwargs else template

            # Reset the execution flag
            _function_executed.set(False)

            try:
                # Call the cached function (either returns cached value or executes _tracked_func)
                result = await original_cached_func(*args, **kwargs)

                # Check if the original function was executed (accurate hit/miss detection)
                duration_ms = (time.time() - start_time) * 1000
                function_was_executed = _function_executed.get(False)

                if function_was_executed:
                    # Cache miss - function was executed
                    _increment_metric("cache.miss")
                    _log_cache_operation(
                        "MISS",
                        key_for_logging,
                        duration_ms=f"{duration_ms:.1f}ms",
                        ttl=ttl_val,
                        cause="cache_miss",
                    )
                else:
                    # Cache hit - function was not executed
                    _increment_metric("cache.hit")
                    _log_cache_operation(
                        "HIT", key_for_logging, duration_ms=f"{duration_ms:.1f}ms", ttl=ttl_val
                    )

                return result

            except Exception as e:
                _increment_metric("cache.error")
                _log_cache_operation("ERROR", key_for_logging, error=str(e))
                raise

        # Try different cashews cache decorator signatures for compatibility
        cache_kwargs = {"tags": tags_func}

        wrapped = None
        error_msgs = []

        # Try to apply cashews decorators with comprehensive error handling
        for attempt_name, attempt_func in [
            ("simple", lambda: _cache.cache(ttl_val, template)(_tracked_func)),
            ("with_tags", lambda: _cache.cache(ttl_val, template, **cache_kwargs)(_tracked_func)),
            (
                "namespaced",
                lambda: _cache.cache(ttl_val, f"{namespace}:{template}" if namespace else template)(
                    _tracked_func
                ),
            ),
        ]:
            try:
                original_cached_func = attempt_func()
                wrapped = _instrumented_wrapper
                break
            except Exception as e:
                error_msgs.append(f"{attempt_name}: {e}")
                continue

        # If all attempts failed, use graceful fallback with full observability
        if wrapped is None:
            logger.info(
                f"Cache decoration failed for {func.__name__}, using observability-only fallback"
            )

            # Fallback: return the original function wrapped with our instrumentation only
            async def _fallback_wrapper(*args, **kwargs):
                _function_executed.set(True)  # Always count as miss since no cache
                start_time = time.time()

                try:
                    key_for_logging = template.format(**kwargs) if kwargs else template
                except Exception:
                    key_for_logging = f"{func.__name__}({','.join(str(k) for k in kwargs.keys())})"

                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                _increment_metric("cache.miss")
                _log_cache_operation(
                    "MISS",
                    key_for_logging,
                    duration_ms=f"{duration_ms:.1f}ms",
                    ttl=ttl_val,
                    cause="cache_unavailable",
                )
                return result

            wrapped = _fallback_wrapper

        # Attach key variants renderer for cache writers - use exact-key deletion first
        setattr(wrapped, "__svc_key_variants__", _build_key_variants_renderer(template))

        # NEW: register this read into a named group (for non-resource warming)
        if group:
            _read_groups[group].append(
                {
                    "getter": wrapped,
                    "key_template": template,  # used for exact deletes if needed
                }
            )

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
    _log_cache_operation("INVALIDATE", f"tags={tags}")

    # Strategy 1: Modern cashews invalidate with tags parameter
    try:
        result = await _cache.invalidate(tags=list(tags))
        count = int(result) if isinstance(result, int) else len(tags)
        _increment_metric("cache.invalidate.count", count)
        return count
    except (TypeError, AttributeError):
        pass
    except Exception as e:
        logger.warning(f"Modern tag invalidation failed: {e}")
        _increment_metric("cache.error")

    # Strategy 2: Legacy cashews invalidate with positional args
    try:
        result = await _cache.invalidate(*tags)
        count = int(result) if isinstance(result, int) else len(tags)
        _increment_metric("cache.invalidate.count", count)
        return count
    except (TypeError, AttributeError):
        pass
    except Exception as e:
        logger.warning(f"Legacy tag invalidation failed: {e}")
        _increment_metric("cache.error")

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
                    _increment_metric("cache.error")
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
                        _increment_metric("cache.error")
                        continue

    _increment_metric("cache.invalidate.count", count)
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
    recache_specs: Optional[Iterable[RecacheSpec]] = None,
    recache_max_concurrency: int = 5,
    warm: Union[bool, str, Iterable[Union[RecacheSpec, Callable]]] = False,  # ← NEW
):
    """
    Cache invalidation decorator for write operations.

    This decorator invalidates cache tags after write operations and
    optionally recaches dependent data to warm the cache.

    Args:
        tags: Cache tags to invalidate (static list or callable)
        recache_specs: Specifications for recaching operations (renamed to avoid shadowing)
        recache_max_concurrency: Maximum concurrent recache operations

    Returns:
        Decorated function with cache invalidation

    Example:
        @cache_write(
            tags=lambda *, user_id, **__: [f"user:{user_id}"],
            recache_specs=[recache(get_user_profile, include=["user_id"])]
        )
        async def update_user(*, user_id: int, data: dict):
            return await save_user(user_id, data)
    """

    def _resolve_tags(func, *args, **kwargs) -> list[str]:
        """Resolve tags from static list or callable."""
        try:
            if callable(tags):
                result = tags(*args, **kwargs)
                resolved_tags = list(result) if result is not None else []
            else:
                resolved_tags = list(tags)

            # Log resolved tags for debugging
            if resolved_tags and _DEBUG_MODE:
                func_name = getattr(func, "__name__", "unknown")
                logger.debug(f"[TAGS] func={func_name} tags={resolved_tags}")

            return resolved_tags
        except Exception as e:
            logger.error(f"Failed to resolve cache tags: {e}")
            _increment_metric("cache.error")
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
                    _increment_metric("cache.error")
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
                        _increment_metric("cache.error")

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
                start_time = time.time()
                try:
                    getter, call_kwargs = _build_getter_kwargs(spec, mut_args, mut_kwargs)

                    # Delete specific cache keys if RecachePlan has key template - prefer exact deletion
                    if isinstance(spec, RecachePlan) and spec.key is not None:
                        # Use exact key variants if available
                        if hasattr(getter, "__svc_key_variants__"):
                            key_variants = getter.__svc_key_variants__(**call_kwargs)
                        else:
                            key_variants = _generate_key_variants(spec.key, call_kwargs)

                        for key_variant in key_variants:
                            try:
                                await _cache.delete(key_variant)
                                _log_cache_operation("DELETE", key_variant, cause="recache_prep")
                            except Exception as e:
                                logger.debug(f"Failed to delete cache key {key_variant}: {e}")
                                _increment_metric("cache.error")

                    # Execute the getter to warm the cache
                    await getter(**call_kwargs)

                    # Track warming performance
                    duration_ms = (time.time() - start_time) * 1000
                    _increment_metric("cache.warm.ms", int(duration_ms))
                    _log_cache_operation(
                        "WARM",
                        str(getter.__name__),
                        duration_ms=f"{duration_ms:.1f}ms",
                        params=str(call_kwargs),
                    )

                except Exception as e:
                    logger.error(f"Recache operation failed: {e}")
                    _increment_metric("cache.error")

        # Execute all recache operations concurrently
        await asyncio.gather(*[_run_single_recache(spec) for spec in specs], return_exceptions=True)

    def _decorator(func: Callable[..., Awaitable[Any]]):
        # synthesize additional recache plans from "warm"
        synthesized: list[RecacheSpec] = []

        # Helper to auto-build include list = intersection(mutator kwargs & getter params)
        def _auto_plan(getter: Callable, key_template: Optional[str] = None) -> RecachePlan:
            gparams = set(signature(getter).parameters.keys())
            # we don't have concrete kwargs here; choose safe heuristic: take all mutator params that getter understands
            mparams = set(signature(func).parameters.keys())
            include = sorted(gparams & mparams)
            return recache(getter, include=include, key=key_template)

        # Case A: warm by group name
        if isinstance(warm, str) and warm:
            for entry in _read_groups.get(warm, []):
                synthesized.append(_auto_plan(entry["getter"], entry["key_template"]))

        # Case B: warm by explicit list of getters / recache plans
        elif isinstance(warm, (list, tuple)):
            for item in warm:
                if isinstance(item, RecachePlan):
                    synthesized.append(item)
                elif callable(item):
                    synthesized.append(
                        _auto_plan(item, getattr(item, "__svc_key_template__", None))
                    )
                else:
                    logger.warning(f"Unsupported warm entry: {item!r}")

        # Merge user-provided recache_specs with synthesized
        merged_recache_specs = recache_specs
        if synthesized:
            merged_recache_specs = (list(recache_specs) if recache_specs else []) + synthesized

        async def _wrapped(*args, **kwargs):
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
                _increment_metric("cache.error")
            finally:
                # Execute recache operations (always run, even if invalidation fails)
                if recache_specs:
                    try:
                        await _execute_recache(recache_specs, *args, **kwargs)
                    except Exception as e:
                        logger.error(f"Cache recaching failed: {e}")
                        _increment_metric("cache.error")

            if merged_recache_specs:
                try:
                    await _execute_recache(merged_recache_specs, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Cache recaching failed: {e}")
                    _increment_metric("cache.error")
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
        self.name = name.strip().lower()
        self.id_field = id_field
        # Registry of reads so we can warm them later when warm=True on writes
        # Each entry: {"getter": <callable>, "key_template": "<template string>"}
        self._read_registry: list[dict[str, Any]] = []

    def _tags(self, **kwargs) -> list[str]:
        _id = kwargs[self.id_field]
        # Keep your existing two-level tag strategy: entity kind + entity instance
        return [self.name, f"{self.name}:{_id}"]

    def _key_base(self) -> tuple[str, ...]:
        # Use a simpler key format that cashews can understand
        return (self.name, f"{{{self.id_field}}}")

    def cache_read(
        self,
        *,
        suffix: Optional[Union[str, tuple[str, ...]]] = None,
        ttl: Optional[int] = None,
        early_ttl: Optional[int] = None,
        refresh: bool = False,
        smooth_expiry: bool = False,
    ):
        """
        Cache decorator for resource read operations.

        Registers the wrapped getter in a per-resource registry so writes with
        warm=True can automatically recache all reads for the same entity.
        """
        parts: list[str] = list(self._key_base())
        if suffix:
            if isinstance(suffix, tuple):
                parts.extend(suffix)
            else:
                parts.append(str(suffix))

        # Create the key template as a simple string for cashews
        key_template = ":".join(parts)

        # Build the actual decorator using your top-level cache_read - ensures namespace consistency
        decorator = cache_read(
            key=key_template,  # Use string instead of tuple
            ttl=ttl,
            tags=lambda **kw: self._tags(**kw),
            early_ttl=early_ttl,
            refresh=refresh,
            smooth_expiry=smooth_expiry,
        )

        def _wrap(func: Callable[..., Awaitable[Any]]):
            # Enforce keyword-only ID parameter convention
            _enforce_keyword_only_id(func, self.id_field)

            wrapped = decorator(func)

            # Record for future warm-ups: getter + concrete template
            # The top-level cache_read already publishes __svc_key_variants__
            # for exact-key deletion; we keep the human template too.
            template_str = ":".join(parts)
            self._read_registry.append({"getter": wrapped, "key_template": template_str})
            return wrapped

        return _wrap

    def cache_write(
        self,
        *,
        recache_specs: Optional[Iterable[RecacheSpec]] = None,  # Fixed name shadowing
        recache_max_concurrency: int = 5,
        warm: bool = False,
    ):
        """
        Cache invalidation decorator for resource write operations.

        If warm=True, automatically recache all registered reads for this resource
        (same id_field) with no specs required.
        """
        # If warm=True, synthesize recache plans from the registry
        synthesized: list[RecacheSpec] = []
        if warm and self._read_registry:
            for entry in self._read_registry:
                getter = entry["getter"]
                template = entry["key_template"]
                # Use the top-level recache(...) factory to delete exact key variants then warm
                synthesized.append(
                    recache(
                        getter,
                        include=[self.id_field],  # pass through id
                        key=template,  # delete exact key variants before warm
                    )
                )

        # Merge user-provided recache specs (if any) with synthesized ones
        merged_recache_specs: Optional[Iterable[RecacheSpec]] = recache_specs
        if synthesized:
            merged_recache_specs = (list(recache_specs) if recache_specs else []) + synthesized

        def _wrap_with_validation(func: Callable[..., Awaitable[Any]]):
            # Enforce keyword-only ID parameter convention
            _enforce_keyword_only_id(func, self.id_field)

            # Delegate to top-level cache_write, preserving your tag strategy
            return cache_write(
                tags=lambda **kw: self._tags(**kw),
                recache_specs=merged_recache_specs,
                recache_max_concurrency=recache_max_concurrency,
            )(func)

        return _wrap_with_validation


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
