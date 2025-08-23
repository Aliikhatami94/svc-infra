from __future__ import annotations

# Backward-compat shim: re-export FastAPI integration from new location
from .integration.fastapi import attach_db as attach_db  # noqa: F401
