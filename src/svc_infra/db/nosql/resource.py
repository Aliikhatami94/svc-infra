from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from pymongo import IndexModel
else:
    try:
        from pymongo import IndexModel
    except ModuleNotFoundError:
        # Minimal runtime stub so importing svc_infra works without optional Mongo deps.
        class IndexModel:  # type: ignore[no-redef]
            pass


def _snake(name: str) -> str:
    import re

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")


def _default_collection_for(model: type) -> str:
    base = _snake(getattr(model, "__name__", "item"))
    return base if base.endswith("s") else base + "s"


def get_collection_name(document_model: type) -> str:
    name = getattr(document_model, "__collection__", None)
    return (
        name.strip()
        if isinstance(name, str) and name.strip()
        else _default_collection_for(document_model)
    )


IndexAlias = dict[str, Any]  # dict alias normalized to IndexModel later


@dataclass
class NoSqlResource:
    """
    Mongo resource declaration used by API & CLI.
    Define indexes here (either IndexModel or simple alias dicts).
    """

    # API mounting
    collection: str | None = None
    prefix: str = ""
    document_model: type[Any] | None = None

    # optional Pydantic schemas (auto-derived if omitted)
    read_schema: type[Any] | None = None
    create_schema: type[Any] | None = None
    update_schema: type[Any] | None = None

    # behavior
    search_fields: Sequence[str] | None = None
    tags: list[str] | None = None
    id_field: str = "_id"
    soft_delete: bool = False
    soft_delete_field: str = "deleted_at"
    soft_delete_flag_field: str | None = None

    # custom wiring
    service_factory: Callable[[Any], Any] | None = None

    # generated schema naming and exclusions
    read_name: str | None = None
    create_name: str | None = None
    update_name: str | None = None
    create_exclude: tuple[str, ...] = ("_id",)
    read_exclude: tuple[str, ...] = ()
    update_exclude: tuple[str, ...] = ()

    # NEW: indexes defined per collection (normalized to IndexModel at prepare time)
    indexes: Iterable[IndexModel | IndexAlias] | None = None

    def __post_init__(self):
        if not self.collection and self.document_model:
            self.collection = get_collection_name(self.document_model)

    def resolved_collection(self) -> str:
        if self.collection:
            return self.collection
        if self.document_model:
            return get_collection_name(self.document_model)
        raise ValueError(
            "No collection name resolved. Set `collection=` or define a document_model with __collection__."
        )
