"""
Cache module providing decorators and utilities for caching operations.

This module offers high-level decorators for read/write caching, cache invalidation,
recaching strategies, and resource-based cache management.
"""

# Backend setup
from .backend import alias, setup_cache, wait_ready

# Core decorators and utilities
from .decorators import cache_read, cache_write, cached, init_cache, init_cache_async, mutates

# Recaching functionality
from .recache import RecachePlan, RecacheSpec, execute_recache, recache

# Resource management
from .resources import Resource, entity, resource

# Tag invalidation
from .tags import invalidate_tags

# TTL utilities
from .ttl import validate_ttl

__all__ = [
    # Core decorators
    "cache_read",
    "cached",
    "cache_write",
    "mutates",
    # Initialization
    "init_cache",
    "init_cache_async",
    # Recaching
    "RecachePlan",
    "RecacheSpec",
    "recache",
    "execute_recache",
    # Resource management
    "Resource",
    "resource",
    "entity",
    # Tag invalidation
    "invalidate_tags",
    # TTL utilities
    "validate_ttl",
    # Backend
    "setup_cache",
    "wait_ready",
    "alias",
]
