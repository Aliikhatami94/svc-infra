from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Column
from sqlalchemy.orm import Mapper, class_mapper

from svc_infra.db.crud_schema import FieldSpec, make_crud_schemas_from_specs


def _sa_columns(model: type[object]) -> list[Column]:
    mapper: Mapper = class_mapper(model)  # raises if not a mapped class
    return list(mapper.columns)


def _py_type(col: Column) -> type:
    # Prefer SQLAlchemy-provided python_type when available
    if getattr(col.type, "python_type", None):
        return col.type.python_type  # type: ignore[no-any-return]

    from datetime import date, datetime
    from typing import Any as _Any
    from uuid import UUID

    from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, Text

    try:
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # type: ignore
    except Exception:  # pragma: no cover
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
    """Heuristics for excluding columns from Create schema."""
    if col.primary_key:
        return True
    if col.server_default is not None:
        return True
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

    specs: list[FieldSpec] = []
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

        specs.append(
            FieldSpec(
                name=name,
                typ=T,
                required_for_create=bool(
                    is_required and name not in explicit_excludes and not _exclude_from_create(col)
                ),
                exclude_from_create=bool(name in explicit_excludes or _exclude_from_create(col)),
                exclude_from_read=bool(name in read_ex),
                exclude_from_update=bool(name in update_ex),
            )
        )

    return make_crud_schemas_from_specs(
        specs=specs,
        read_name=read_name or f"{model.__name__}Read",
        create_name=create_name or f"{model.__name__}Create",
        update_name=update_name or f"{model.__name__}Update",
    )
