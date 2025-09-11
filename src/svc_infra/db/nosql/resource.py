from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Type


@dataclass
class NoSqlResource:
    """
    Mirrors SqlResource but for Mongo.
    - You provide collection name, optional service factory, and (optionally)
      explicit Pydantic schemas. If not provided, we'll derive from a BaseModel
      "document model" via management.make_document_crud_schemas.
    """

    collection: str
    prefix: str
    # optional Pydantic schemas
    read_schema: Optional[Type[Any]] = None
    create_schema: Optional[Type[Any]] = None
    update_schema: Optional[Type[Any]] = None
    # optional convenience to derive schemas from a Pydantic BaseModel
    document_model: Optional[Type[Any]] = None
    # behavior
    search_fields: Optional[Sequence[str]] = None
    tags: Optional[list[str]] = None
    id_field: str = "_id"
    soft_delete: bool = False
    soft_delete_field: str = "deleted_at"
    soft_delete_flag_field: Optional[str] = None
    # custom wiring
    service_factory: Optional[Callable[[Any], Any]] = None
    # naming overrides for generated schemas
    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None
    # fields to exclude from Create/Update when auto-generating
    create_exclude: tuple[str, ...] = ("_id",)
    read_exclude: tuple[str, ...] = ()
    update_exclude: tuple[str, ...] = ()
