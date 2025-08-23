from __future__ import annotations

# Re-export FastAPI integration helpers for convenient imports
from .fastapi import (
    attach_db,
    get_engine,
    get_session,
    get_uow,
    EngineDep,
    SessionDep,
    UoWDep,
)

__all__ = [
    "attach_db",
    "get_engine",
    "get_session",
    "get_uow",
    "EngineDep",
    "SessionDep",
    "UoWDep",
]

