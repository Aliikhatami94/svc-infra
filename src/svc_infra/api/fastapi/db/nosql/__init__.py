from __future__ import annotations

from typing import Any


def _missing_mongo_dependency() -> ModuleNotFoundError:
    return ModuleNotFoundError(
        "MongoDB support is an optional dependency. Install pymongo (and motor) to use "
        "Mongo helpers like add_mongo_db/add_mongo_health/add_mongo_resources."
    )


try:
    from .mongo.add import add_mongo_db, add_mongo_health, add_mongo_resources
except ModuleNotFoundError as exc:
    mongo_import_error = exc

    # NOTE: pymongo provides `bson`, which can be absent in minimal installs/CI.
    # We keep imports working for non-mongo users/tests by providing stubs.
    def add_mongo_db(*args: Any, **kwargs: Any) -> Any:
        raise _missing_mongo_dependency() from mongo_import_error

    def add_mongo_health(*args: Any, **kwargs: Any) -> Any:
        raise _missing_mongo_dependency() from mongo_import_error

    def add_mongo_resources(*args: Any, **kwargs: Any) -> Any:
        raise _missing_mongo_dependency() from mongo_import_error


__all__ = [
    # MongoDB
    "add_mongo_resources",
    "add_mongo_db",
    "add_mongo_health",
]
