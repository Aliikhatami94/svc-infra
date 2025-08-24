from __future__ import annotations
from typing import Any, Optional, Type
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.orm import Mapper, class_mapper
from sqlalchemy import Column

def _sa_columns(model: type) -> list[Column]:
    mapper: Mapper = class_mapper(model)  # raises if not a mapped class
    return [model.__table__.c[name] for name in mapper.columns.keys()]

def _py_type(col: Column) -> type:
    # very small map; expand if you need more types
    from sqlalchemy import String, Text, Integer, Boolean
    import uuid
    if getattr(col.type, "python_type", None):
        return col.type.python_type  # works for many types incl UUID
    if isinstance(col.type, (String, Text)):
        return str
    if isinstance(col.type, Integer):
        return int
    if isinstance(col.type, Boolean):
        return bool
    return Any

def make_crud_schemas(
        model: type,
        *,
        create_exclude: tuple[str, ...] = ("id",),
        update_optional: tuple[str, ...] | None = None,
        read_name: str | None = None,
        create_name: str | None = None,
        update_name: str | None = None,
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    cols = _sa_columns(model)
    ann_read = {}
    ann_create = {}
    ann_update = {}

    for col in cols:
        name = col.name
        T = _py_type(col)
        is_required = not col.nullable and col.default is None and col.server_default is None and not col.primary_key

        # Read: literal column types, always present (let Pydantic read from SA objects)
        ann_read[name] = (T | None if col.nullable else T, None)

        # Create: exclude some (like id), otherwise required if column is required
        if name not in create_exclude:
            ann_create[name] = ((T | None) if not is_required else T, None if not is_required else ...)

        # Update: everything optional unless narrowed by update_optional
        ann_update[name] = (Optional[T], None)

    Read = create_model(read_name or f"{model.__name__}Read", **ann_read)  # type: ignore
    Create = create_model(create_name or f"{model.__name__}Create", **ann_create)  # type: ignore
    Update = create_model(update_name or f"{model.__name__}Update", **ann_update)  # type: ignore

    # allow ORM objects
    for M in (Read, Create, Update):
        M.model_config = ConfigDict(from_attributes=True)
        M.model_rebuild()

    return Read, Create, Update