from __future__ import annotations

from typing import Any

from .repository import NoSqlRepository


def _missing_mongo_dependency() -> ModuleNotFoundError:
    return ModuleNotFoundError(
        "MongoDB support is an optional dependency. Install pymongo (and motor) to use "
        "NoSQL Mongo helpers like NoSqlResource and mongo prepare commands."
    )


try:
    from svc_infra.db.nosql.resource import NoSqlResource
except ModuleNotFoundError as exc:
    _mongo_import_error = exc

    class NoSqlResource:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise _missing_mongo_dependency() from _mongo_import_error


__all__ = [
    "NoSqlResource",
    "NoSqlRepository",
]
