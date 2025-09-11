from __future__ import annotations

from typing import Sequence

# Environment variable names to look up for Mongo URL
DEFAULT_MONGO_ENV_VARS: Sequence[str] = (
    "MONGO_URL",
    "MONGODB_URL",
)

# Default DB name envs (optional convenience)
DEFAULT_MONGO_DB_ENV_VARS: Sequence[str] = (
    "MONGO_DB",
    "MONGODB_DB",
    "MONGO_DATABASE",
)

__all__ = ["DEFAULT_MONGO_ENV_VARS", "DEFAULT_MONGO_DB_ENV_VARS"]
