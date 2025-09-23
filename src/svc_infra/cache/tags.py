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
