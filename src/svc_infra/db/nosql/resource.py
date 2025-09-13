from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence, Type, Union

from pymongo import IndexModel


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
    collection: Optional[str] = None
    prefix: str = ""
    document_model: Optional[Type[Any]] = None

    # optional Pydantic schemas (auto-derived if omitted)
    read_schema: Optional[Type[Any]] = None
    create_schema: Optional[Type[Any]] = None
    update_schema: Optional[Type[Any]] = None

    # behavior
    search_fields: Optional[Sequence[str]] = None
    tags: Optional[list[str]] = None
    id_field: str = "_id"
    soft_delete: bool = False
    soft_delete_field: str = "deleted_at"
    soft_delete_flag_field: Optional[str] = None

    # custom wiring
    service_factory: Optional[Callable[[Any], Any]] = None

    # generated schema naming and exclusions
    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None
    create_exclude: tuple[str, ...] = ("_id",)
    read_exclude: tuple[str, ...] = ()
    update_exclude: tuple[str, ...] = ()

    # NEW: indexes defined per collection (normalized to IndexModel at prepare time)
    indexes: Optional[Iterable[Union[IndexModel, IndexAlias]]] = None

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
