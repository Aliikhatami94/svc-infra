from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Type


def _snake(name: str) -> str:
    import re

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")


def _default_collection_for(model: type) -> str:
    # pluralize a bit naively; good enough for defaults
    base = _snake(getattr(model, "__name__", "item"))
    return base if base.endswith("s") else base + "s"


def get_collection_name(document_model: type) -> str:
    # prefer explicit __collection__
    name = getattr(document_model, "__collection__", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return _default_collection_for(document_model)


@dataclass
class NoSqlResource:
    """
    Mongo resource declaration used by API & CLI.
    Prefer passing document_model and let collection auto-resolve from its
    __collection__ (or plural snake fallback). Explicit 'collection' still
    overrides for backward compatibility.
    """

    # API mounting
    prefix: str
    document_model: Type[Any]

    # optional overrides / compatibility
    collection: Optional[str] = None

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

    # --- derived ---
    def resolved_collection(self) -> str:
        return self.collection or get_collection_name(self.document_model)
