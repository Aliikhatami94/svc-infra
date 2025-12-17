"""
Cache tag invalidation utilities.

This module provides functionality for invalidating cache entries by tags
with fallback strategies for different cashews versions.
"""

import logging

from cashews import cache as _cache

logger = logging.getLogger(__name__)


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

    # Preserve order while de-duplicating.
    tags_to_delete = list(dict.fromkeys(tags))

    # Cashews supports explicit tag deletion via delete_tags().
    try:
        if hasattr(_cache, "delete_tags"):
            await _cache.delete_tags(*tags_to_delete)
            return len(tags_to_delete)
    except Exception as e:
        logger.warning(f"Cache tag invalidation failed: {e}")

    # Fallback: attempt private per-tag deletion when available.
    deleted = 0
    for tag in tags_to_delete:
        try:
            if hasattr(_cache, "_delete_tag"):
                await _cache._delete_tag(tag)
                deleted += 1
        except Exception as e:
            logger.debug(f"Tag deletion failed for tag {tag}: {e}")

    return deleted
