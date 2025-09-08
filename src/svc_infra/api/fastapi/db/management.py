from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.orm import Mapper, class_mapper
from sqlalchemy import Column


def _sa_columns(model: type[object]) -> list[Column]:
    mapper: Mapper = class_mapper(model)  # raises if not a mapped class
    return list(mapper.columns)


def _py_type(col: Column) -> type:
    # Prefer SQLAlchemy-provided python_type when available
    if getattr(col.type, "python_type", None):
        return col.type.python_type  # type: ignore[no-any-return]

    # Fallback mappings for common types
    from typing import Any as _Any
    from datetime import datetime, date
    from uuid import UUID
    from sqlalchemy import String, Text, Integer, Boolean, DateTime, Date, JSON
    try:
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB  # type: ignore
    except Exception:  # pragma: no cover - optional import
        PG_UUID = None  # type: ignore
        JSONB = None  # type: ignore

    t = col.type
    if PG_UUID is not None and isinstance(t, PG_UUID):
        return UUID
    if isinstance(t, (String, Text)):
        return str
    if isinstance(t, Integer):
        return int
    if isinstance(t, Boolean):
        return bool
    if isinstance(t, (DateTime,)):
        return datetime
    if isinstance(t, (Date,)):
        return date
    if isinstance(t, JSON):
        return dict
    if JSONB is not None and isinstance(t, JSONB):
        return dict
    return _Any


def _exclude_from_create(col: Column) -> bool:
    """Heuristics for excluding columns from Create schema.

    - primary keys
    - server defaults
    - SQL/DB-generated values (onupdate)
    - obvious timestamp names (created_at/updated_at)
    - autogenerating defaults (uuid.uuid4 etc.)
    """
    if col.primary_key:
        return True
    if col.server_default is not None:
        return True
    # default can be a SQLAlchemy DefaultClause or a Python callable/arg
    default = getattr(col, "default", None)
    if getattr(default, "is_sequence", False):
        return True
    if getattr(default, "arg", None):  # e.g., default=uuid.uuid4
        return True
    if col.onupdate is not None:
        return True
    if col.name in {"created_at", "updated_at"}:
        return True
    return False


def make_crud_schemas(
        model: type[object],
        *,
        create_exclude: tuple[str, ...] = ("id",),
        read_name: str | None = None,
        create_name: str | None = None,
        update_name: str | None = None,
        read_exclude: tuple[str, ...] = (),
        update_exclude: tuple[str, ...] = (),
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    cols = _sa_columns(model)
    ann_read: dict[str, tuple[type, object]] = {}
    ann_create: dict[str, tuple[type, object]] = {}
    ann_update: dict[str, tuple[type, object]] = {}

    # Combine explicit excludes with heuristic excludes
    explicit_excludes = set(create_exclude)
    read_ex = set(read_exclude)
    update_ex = set(update_exclude)

    for col in cols:
        name = col.name
        T = _py_type(col)
        is_required = (
                not col.nullable
                and col.default is None
                and col.server_default is None
                and not col.primary_key
        )

        if name not in read_ex:
            ann_read[name] = (T | None if col.nullable else T, None)

        if name not in explicit_excludes and not _exclude_from_create(col):
            ann_create[name] = ((T | None) if not is_required else T, None if not is_required else ...)

        if name not in update_ex:
            ann_update[name] = (Optional[T], None)

    Read = create_model(read_name or f"{model.__name__}Read", **ann_read)   # type: ignore[arg-type]
    Create = create_model(create_name or f"{model.__name__}Create", **ann_create)  # type: ignore[arg-type]
    Update = create_model(update_name or f"{model.__name__}Update", **ann_update)  # type: ignore[arg-type]

    for M in (Read, Create, Update):
        M.model_config = ConfigDict(from_attributes=True)
        M.model_rebuild()

    return Read, Create, Update