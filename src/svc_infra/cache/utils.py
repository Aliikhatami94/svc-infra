"""
Cache utility functions for key generation and hashing.

This module provides utility functions for creating stable cache keys,
hashing complex objects, and formatting key templates.
"""

import hashlib
import json
import logging
from typing import Any, Iterable, Union

logger = logging.getLogger(__name__)


def stable_hash(*args: Any, **kwargs: Any) -> str:
    """
    Generate a stable hash from arbitrary arguments.

    This function creates a deterministic hash that remains consistent
    across different Python sessions and platforms.

    Args:
        *args: Positional arguments to hash
        **kwargs: Keyword arguments to hash

    Returns:
        SHA-1 hash as hexadecimal string

    Example:
        >>> stable_hash("user", 123, status="active")
        'a1b2c3d4e5f6...'
    """
    try:
        # Use JSON serialization for stable, deterministic output
        raw = json.dumps([args, kwargs], default=str, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        # Fallback to repr if JSON serialization fails
        logger.warning(f"JSON serialization failed for hash input, using repr: {e}")
        raw = repr((args, kwargs))

    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def join_key(parts: Iterable[Union[str, int, None]]) -> str:
    """
    Join key parts into a cache key, filtering out empty values.

    Args:
        parts: Iterable of key parts (strings, integers, or None)

    Returns:
        Joined cache key with colons as separators

    Example:
        >>> join_key(["user", 123, "profile"])
        'user:123:profile'
        >>> join_key(["user", None, "", "profile"])
        'user:profile'
    """
    cleaned_parts = []
    for part in parts:
        if part is not None and part != "":
            # Convert to string and strip colons to avoid double separators
            str_part = str(part).strip(":")
            if str_part:
                cleaned_parts.append(str_part)

    return ":".join(cleaned_parts)


def format_tuple_key(key_tuple: tuple[str, ...], **kwargs) -> str:
    """
    Format a tuple of key template parts with provided keyword arguments.

    Args:
        key_tuple: Tuple of key template strings
        **kwargs: Values to substitute in template placeholders

    Returns:
        Formatted cache key

    Raises:
        KeyError: If required template variables are missing

    Example:
        >>> format_tuple_key(("user", "{user_id}", "profile"), user_id=123)
        'user:123:profile'
    """
    try:
        formatted_parts = [part.format(**kwargs) for part in key_tuple]
        return join_key(formatted_parts)
    except KeyError as e:
        logger.error(f"Missing template variable for key formatting: {e}")
        raise
    except Exception as e:
        logger.error(f"Error formatting tuple key: {e}")
        raise ValueError(f"Failed to format key template: {e}") from e


def normalize_cache_key(key: Union[str, tuple[str, ...]], **kwargs) -> str:
    """
    Normalize a cache key from various input formats.

    Args:
        key: Cache key as string or tuple template
        **kwargs: Template variables for tuple keys

    Returns:
        Normalized cache key string

    Example:
        >>> normalize_cache_key("user:123:profile")
        'user:123:profile'
        >>> normalize_cache_key(("user", "{user_id}", "profile"), user_id=123)
        'user:123:profile'
    """
    if isinstance(key, tuple):
        return format_tuple_key(key, **kwargs)
    elif isinstance(key, str):
        if kwargs:
            try:
                return key.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Template variable missing in key '{key}': {e}")
                return key
        return key
    else:
        raise TypeError(f"Cache key must be string or tuple, got {type(key)}")


def validate_cache_key(key: str, max_length: int = 250) -> str:
    """
    Validate and sanitize a cache key.

    Args:
        key: Cache key to validate
        max_length: Maximum allowed key length

    Returns:
        Validated cache key

    Raises:
        ValueError: If key is invalid or too long

    Example:
        >>> validate_cache_key("user:123:profile")
        'user:123:profile'
    """
    if not key or not isinstance(key, str):
        raise ValueError("Cache key must be a non-empty string")

    if len(key) > max_length:
        # Hash long keys to keep them under the limit
        logger.warning(f"Cache key too long ({len(key)} chars), hashing: {key[:50]}...")
        return f"hashed:{stable_hash(key)}"

    # Remove any characters that might cause issues
    sanitized = key.replace("\n", "").replace("\r", "").replace("\t", "")

    if not sanitized:
        raise ValueError("Cache key cannot be empty after sanitization")

    return sanitized
