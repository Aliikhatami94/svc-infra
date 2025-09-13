from __future__ import annotations

from typing import Any, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel

from svc_infra.db.crud_schema import FieldSpec, make_crud_schemas_from_specs

_MUTABLE_ID_FIELDS = {"id", "_id"}
_TS_FIELDS = {"created_at", "updated_at"}


def _is_optional(annotation: Any) -> bool:
    return get_origin(annotation) is Optional or (
        get_origin(annotation) is Union and type(None) in get_args(annotation)
    )


def make_document_crud_schemas(
    document_model: Type[BaseModel],
    *,
    create_exclude: tuple[str, ...] = ("_id",),
    read_name: str | None = None,
    create_name: str | None = None,
    update_name: str | None = None,
    read_exclude: tuple[str, ...] = (),
    update_exclude: tuple[str, ...] = (),
    json_encoders: dict[type, Any] | None = None,  # allow ObjectId encoder if desired
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    """
    Derive (Read, Create, Update) from a Pydantic document model (Mongo).
    - Read: all fields optional (unless excluded)
    - Create: exclude ID/timestamps and any in create_exclude; required mirrors document "required"
    - Update: all optional (unless excluded)
    """
    annotations = document_model.model_fields  # Pydantic v2
    explicit_create_ex = set(create_exclude) | _MUTABLE_ID_FIELDS | _TS_FIELDS
    read_ex = set(read_exclude)
    update_ex = set(update_exclude)

    specs: list[FieldSpec] = []
    for name, field in annotations.items():
        T = field.annotation or Any
        required = field.is_required()
        specs.append(
            FieldSpec(
                name=name,
                typ=T,
                required_for_create=bool(
                    required and not _is_optional(T) and name not in explicit_create_ex
                ),
                exclude_from_create=(name in explicit_create_ex),
                exclude_from_read=(name in read_ex),
                exclude_from_update=(name in update_ex),
            )
        )

    return make_crud_schemas_from_specs(
        specs=specs,
        read_name=read_name or f"{document_model.__name__}Read",
        create_name=create_name or f"{document_model.__name__}Create",
        update_name=update_name or f"{document_model.__name__}Update",
        json_encoders=json_encoders,
    )
