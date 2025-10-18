from __future__ import annotations

import logging
from typing import Optional

from cashews import cache as _cache

# Module-level logger
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_PREFIX = "svc"
DEFAULT_VERSION = "v1"
DEFAULT_READINESS_TIMEOUT = 5.0
PROBE_KEY_SUFFIX = "__probe__"
PROBE_VALUE = "ok"
PROBE_EXPIRE_SECONDS = 3

# Global state
_current_prefix: str = DEFAULT_PREFIX
_current_version: str = DEFAULT_VERSION


def alias() -> str:
    """
    Get the human-readable namespace label.

    Returns:
        Formatted namespace string like "svc:v1"
    """
    return f"{_current_prefix}:{_current_version}"


def _full_prefix() -> str:
    """
    Get the actual key prefix applied by cashews.

    Returns:
        Formatted prefix string with trailing colon like "svc:v1:"
    """
    return f"{_current_prefix}:{_current_version}:"


def setup_cache(
    url: Optional[str] = None,
    *,
    prefix: Optional[str] = None,
    version: Optional[str] = None,
):
    """
    Configure Cashews and set a global key prefix for namespacing.

    Args:
        url: Cache backend URL (Redis, etc.). If None, uses default configuration
        prefix: Cache key prefix override. Defaults to "svc"
        version: Cache version override. Defaults to "v1"

    Returns:
        Awaitable setup result from cashews that callers may await or not

    Example:
        Basic setup:
        >>> setup_cache()

        With custom Redis URL:
        >>> setup_cache(url="redis://localhost:6379")

        With custom namespace:
        >>> setup_cache(prefix="myapp", version="v2")
    """
    global _current_prefix, _current_version

    # Update global state if new values provided
    if prefix is not None:
        _current_prefix = prefix
        logger.info(f"Cache prefix updated to: {_current_prefix}")

    if version is not None:
        _current_version = version
        logger.info(f"Cache version updated to: {_current_version}")

    # Setup backend connection
    # Newer cashews versions require an explicit settings_url; default to in-memory
    # backend when no URL is provided so acceptance/unit tests work out of the box.
    try:
        settings_url = url or "mem://"
        setup_awaitable = _cache.setup(settings_url)
        logger.info(f"Cache backend setup initiated with URL: {settings_url}")
    except Exception as e:
        logger.error(f"Failed to setup cache backend: {e}")
        raise

    return setup_awaitable


async def wait_ready(timeout: float = DEFAULT_READINESS_TIMEOUT) -> None:
    """
    Wait for cache to be ready by performing a readiness probe.

    Args:
        timeout: Maximum time to wait for readiness (not currently used by probe)

    Raises:
        RuntimeError: If the readiness probe fails

    Example:
        >>> await wait_ready()
        >>> await wait_ready(timeout=10.0)
    """
    probe_key = f"{_full_prefix()}{PROBE_KEY_SUFFIX}"

    try:
        # Set probe value
        await _cache.set(probe_key, PROBE_VALUE, expire=PROBE_EXPIRE_SECONDS)
        logger.debug(f"Set readiness probe key: {probe_key}")

        # Verify probe value
        retrieved_value = await _cache.get(probe_key)

        if retrieved_value != PROBE_VALUE:
            error_msg = (
                f"Cache readiness probe failed. Expected '{PROBE_VALUE}', got '{retrieved_value}'"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("Cache readiness probe successful")

    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        error_msg = f"Cache readiness probe encountered error: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


async def shutdown_cache() -> None:
    """
    Gracefully shutdown the cache backend.

    This method handles exceptions gracefully to ensure shutdown doesn't fail.
    """
    try:
        await _cache.close()
        logger.info("Cache backend shutdown successfully")
    except Exception as e:
        logger.warning(f"Error during cache shutdown (ignored): {e}")


def instance():
    """
    Get the underlying cashews cache instance.

    Returns:
        The cashews cache instance for direct access

    Warning:
        Direct access to the cache instance bypasses the namespace prefix.
        Use with caution in production code.
    """
    return _cache
