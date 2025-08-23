from __future__ import annotations

# Backward-compat shim: expose cache interfaces from new package
from .cache.base import BaseCache, NullCache, InMemoryCache  # noqa: F401

__all__ = ["BaseCache", "NullCache", "InMemoryCache"]
