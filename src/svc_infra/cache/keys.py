"""
Cache key generation and management utilities.

This module provides functionality for building cache keys and templates
with version-resilient handling and namespace support.
"""

import logging
from typing import Callable, Union

from svc_infra.cache.backend import alias as _alias

from .utils import validate_cache_key

logger = logging.getLogger(__name__)


def build_key_template(key: Union[str, tuple[str, ...]]) -> str:
    """Convert key to template string."""
    if isinstance(key, tuple):
        parts = [part for part in key if part]
        return ":".join(part.strip(":") for part in parts)
    return str(key)


def create_tags_function(tags_param):
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


def build_key_variants_renderer(template: str) -> Callable[..., list[str]]:
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


def resolve_tags(tags, *args, **kwargs) -> list[str]:
    """Resolve tags from static list or callable and render templates with kwargs.

    Supports entries like "thing:{id}" which will be formatted using provided kwargs.
    Non-string items are passed through as str(). Missing keys are skipped with a warning.
    """
    try:
        # 1) Obtain raw tags list
        if callable(tags):
            raw = tags(*args, **kwargs)
            raw_list = list(raw) if raw is not None else []
        else:
            raw_list = list(tags)

        # 2) Render any templates using kwargs
        rendered: list[str] = []
        for t in raw_list:
            try:
                if isinstance(t, str) and ("{" in t and "}" in t):
                    rendered.append(t.format(**kwargs))
                else:
                    rendered.append(str(t))
            except KeyError as e:
                logger.warning(f"Tag template missing key {e} in '{t}'")
            except Exception as e:
                logger.warning(f"Failed to render tag '{t}': {e}")
        return [r for r in rendered if r]
    except Exception as e:
        logger.error(f"Failed to resolve cache tags: {e}")
        return []
