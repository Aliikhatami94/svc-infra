from __future__ import annotations

# Backward-compat shim: forward FastAPI deps from new location
from .integration.fastapi import (
    get_engine,
    get_session,
    get_uow,
    EngineDep,
    SessionDep,
    UoWDep,
)

__all__ = [
    "get_engine",
    "get_session",
    "get_uow",
    "EngineDep",
    "SessionDep",
    "UoWDep",
]
