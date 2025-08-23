from __future__ import annotations

# Backward-compat shim: expose Repository from new package path
from .repository.base import Repository

__all__ = ["Repository"]
