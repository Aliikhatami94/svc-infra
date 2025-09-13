from __future__ import annotations

from typing import Any, Optional, Type, Union, get_args, get_origin

from bson import ObjectId
from pydantic import BaseModel

from svc_infra.db.crud_schema import FieldSpec, make_crud_schemas_from_specs
from svc_infra.db.nosql.types import PyObjectId

_MUTABLE_ID_FIELDS = {"id", "_id"}
_TS_FIELDS = {"created_at", "updated_at"}


def _is_optional(annotation: Any) -> bool:
    return get_origin(annotation) is Optional or (
        get_origin(annotation) is Union and type(None) in get_args(annotation)
    )


def _unwrap_union(annotation: Any) -> set[type]:
    """
    Return the set of non-None types inside a Union/Optional[T] or {annotation} if not a Union.
    """
    origin = get_origin(annotation)
    if origin is Union:
        return {t for t in get_args(annotation) if t is not type(None)}  # noqa: E721
    return {annotation} if annotation is not None else set()


def _is_objectid_like(annotation: Any) -> bool:
    """
    True if the annotation is (or wraps) bson.ObjectId / PyObjectId.
    """
    inner = _unwrap_union(annotation)
    return any(t in (ObjectId, PyObjectId) for t in inner)


def make_document_crud_schemas(
    document_model: Type[BaseModel],
    *,
    create_exclude: tuple[str, ...] = ("_id",),
    read_name: str | None = None,
    create_name: str | None = None,
    update_name: str | None = None,
    read_exclude: tuple[str, ...] = (),
    update_exclude: tuple[str, ...] = (),
    json_encoders: dict[type, Any] | None = None,
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    """
    Derive (Read, Create, Update) from a Pydantic document model (Mongo).

    Key behavior:
    - Read: expose fields, but coerce any ObjectId-like types to `str` so responses are JSON-safe.
    - Create: exclude ID/timestamps and anything in create_exclude; required mirrors document model.
    - Update: all optional; ObjectId-like types coerced to `str` for JSON safety.
    """
    annotations = document_model.model_fields  # Pydantic v2
    explicit_create_ex = set(create_exclude) | _MUTABLE_ID_FIELDS | _TS_FIELDS
    read_ex = set(read_exclude)
    update_ex = set(update_exclude)

    specs: list[FieldSpec] = []
    for name, field in annotations.items():
        T = field.annotation or Any
        required = field.is_required()

        # Coerce ObjectId-ish to `str` for READ/UPDATE to avoid custom encoder headaches.
        # (Create path ignores IDs anyway due to explicit_create_ex.)
        T_out = str if _is_objectid_like(T) else T

        specs.append(
            FieldSpec(
                name=name,
                typ=T_out,
                required_for_create=bool(
                    required and not _is_optional(T) and name not in explicit_create_ex
                ),
                exclude_from_create=(name in explicit_create_ex),
                exclude_from_read=(name in read_ex),
                exclude_from_update=(name in update_ex),
            )
        )

    # Backstop encoders in case any exotic types slip through
    encoders = {ObjectId: str, PyObjectId: str}
    if json_encoders:
        encoders.update(json_encoders)

    return make_crud_schemas_from_specs(
        specs=specs,
        read_name=read_name or f"{document_model.__name__}Read",
        create_name=create_name or f"{document_model.__name__}Create",
        update_name=update_name or f"{document_model.__name__}Update",
        json_encoders=encoders,
    )
