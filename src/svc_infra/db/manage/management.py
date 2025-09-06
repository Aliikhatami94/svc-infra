from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.orm import Mapper, class_mapper
from sqlalchemy import Column


def _sa_columns(model: type[object]) -> list[Column]:
    mapper: Mapper = class_mapper(model)  # raises if not a mapped class
    return list(mapper.columns)


def _py_type(col: Column) -> type:
    from sqlalchemy import String, Text, Integer, Boolean
    if getattr(col.type, "python_type", None):
        return col.type.python_type
    if isinstance(col.type, (String, Text)):
        return str
    if isinstance(col.type, Integer):
        return int
    if isinstance(col.type, Boolean):
        return bool
    return Any


def make_crud_schemas(
        model: type[object],
        *,
        create_exclude: tuple[str, ...] = ("id",),
        read_name: str | None = None,
        create_name: str | None = None,
        update_name: str | None = None,
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    cols = _sa_columns(model)
    ann_read: dict[str, tuple[type, object]] = {}
    ann_create: dict[str, tuple[type, object]] = {}
    ann_update: dict[str, tuple[type, object]] = {}

    for col in cols:
        name = col.name
        T = _py_type(col)
        is_required = (
                not col.nullable
                and col.default is None
                and col.server_default is None
                and not col.primary_key
        )

        ann_read[name] = (T | None if col.nullable else T, None)

        if name not in create_exclude:
            ann_create[name] = ((T | None) if not is_required else T, None if not is_required else ...)

        ann_update[name] = (Optional[T], None)

    Read = create_model(read_name or f"{model.__name__}Read", **ann_read)   # type: ignore[arg-type]
    Create = create_model(create_name or f"{model.__name__}Create", **ann_create)  # type: ignore[arg-type]
    Update = create_model(update_name or f"{model.__name__}Update", **ann_update)  # type: ignore[arg-type]

    for M in (Read, Create, Update):
        M.model_config = ConfigDict(from_attributes=True)
        M.model_rebuild()

    return Read, Create, Update