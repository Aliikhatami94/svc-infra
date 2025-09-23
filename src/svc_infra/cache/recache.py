"""
Cache recaching functionality and utilities.

This module provides support for cache warming operations after invalidation,
including recache plans and execution strategies.
"""

import asyncio
import logging
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias

from .utils import normalize_cache_key, validate_cache_key

logger = logging.getLogger(__name__)


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


def generate_key_variants(
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


def build_getter_kwargs(
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


async def execute_recache(
    specs: Iterable[RecacheSpec], *mut_args, max_concurrency: int = 5, **mut_kwargs
) -> None:
    """Execute recache operations with concurrency control."""
    if not specs:
        return

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_single_recache(spec: RecacheSpec) -> None:
        async with semaphore:
            try:
                getter, call_kwargs = build_getter_kwargs(spec, mut_args, mut_kwargs)

                # Delete specific cache keys if RecachePlan has key template
                if isinstance(spec, RecachePlan) and spec.key is not None:
                    key_variants = generate_key_variants(spec.key, call_kwargs)
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
