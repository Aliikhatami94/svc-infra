"""
Cache TTL (Time To Live) configuration module.

This module provides standardized cache expiration times that can be configured
via environment variables with sensible defaults.
"""

import os
from typing import Optional


def _get_env_int(key: str, default: int) -> int:
    """
    Safely retrieve an integer value from environment variables.

    Args:
        key: Environment variable name
        default: Default value if env var is not set or invalid

    Returns:
        Integer value from environment or default
    """
    try:
        value = os.getenv(key)
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        # Log warning in production, but don't fail
        return default


# Standard TTL values (in seconds)
TTL_DEFAULT: int = _get_env_int("CACHE_TTL_DEFAULT", 300)  # 5 minutes
TTL_SHORT: int = _get_env_int("CACHE_TTL_SHORT", 30)  # 30 seconds
TTL_LONG: int = _get_env_int("CACHE_TTL_LONG", 3600)  # 1 hour


def get_ttl(duration_type: str) -> Optional[int]:
    """
    Get TTL value by duration type name.

    Args:
        duration_type: One of 'default', 'short', 'long'

    Returns:
        TTL value in seconds, or None if invalid type

    Example:
        >>> get_ttl('short')
        30
        >>> get_ttl('default')
        300
    """
    ttl_map = {
        "default": TTL_DEFAULT,
        "short": TTL_SHORT,
        "long": TTL_LONG,
    }
    return ttl_map.get(duration_type.lower())


def validate_ttl(ttl: Optional[int]) -> int:
    """
    Validate and normalize a TTL value.

    Args:
        ttl: TTL value to validate (can be None)

    Returns:
        Valid TTL value (uses default if None or invalid)

    Example:
        >>> validate_ttl(None)
        300
        >>> validate_ttl(-1)
        300
        >>> validate_ttl(60)
        60
    """
    if ttl is None or ttl < 0:
        return TTL_DEFAULT
    return ttl
