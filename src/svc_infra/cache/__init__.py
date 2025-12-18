"""
Cache module providing decorators and utilities for caching operations.

This module offers high-level decorators for read/write caching, cache invalidation,
and resource-based cache management.
"""

from .add import add_cache

# Cache instance access for object-oriented usage
from .backend import get_cache

# Core decorators - main public API
from .decorators import (
    cache_read,
    cache_write,
    cached,  # alias for cache_read
    init_cache,
    init_cache_async,
    mutates,  # alias for cache_write
)

# Recaching functionality for advanced use cases
from .recache import RecachePlan, recache

# Resource management for entity-based caching
from .resources import (
    entity,  # legacy alias
    resource,
)

__all__ = [
    # Primary decorators developers use
    "cache_read",
    "cached",
    "cache_write",
    "mutates",
    # Cache initialization
    "init_cache",
    "init_cache_async",
    # Advanced recaching
    "RecachePlan",
    "recache",
    # Resource-based caching
    "resource",
    "entity",
    # Easy integration helper
    "add_cache",
    # Cache instance access
    "get_cache",
]
