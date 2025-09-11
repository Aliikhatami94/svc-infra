from __future__ import annotations

from typing import Any, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, create_model

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
) -> tuple[Type[BaseModel], Type[BaseModel], Type[BaseModel]]:
    """
    Build (Read, Create, Update) from a Pydantic BaseModel that models a Mongo document.
    - Read: all fields optional in output (consistent with SQL Read leniency)
    - Create: exclude create_exclude + timestamps; requiredness mirrors model (if not optional)
    - Update: all Optional
    """
    annotations = document_model.model_fields  # Pydantic v2
    ann_read: dict[str, tuple[type, object]] = {}
    ann_create: dict[str, tuple[type, object]] = {}
    ann_update: dict[str, tuple[type, object]] = {}

    explicit_create_ex = set(create_exclude) | _MUTABLE_ID_FIELDS | _TS_FIELDS
    read_ex = set(read_exclude)
    update_ex = set(update_exclude)

    for name, field in annotations.items():
        T = field.annotation or Any
        required = field.is_required()

        # Read: include unless excluded; make Optional
        if name not in read_ex:
            ann_read[name] = ((T | None), None)  # type: ignore[operator]

        # Create: skip excluded list; make required if model required & not excluded
        if name not in explicit_create_ex:
            is_required = required and not _is_optional(T)
            ann_create[name] = (T, ... if is_required else None)

        # Update: include unless excluded; always Optional
        if name not in update_ex:
            ann_update[name] = ((T | None), None)  # type: ignore[operator]

    Read = create_model(read_name or f"{document_model.__name__}Read", **ann_read)  # type: ignore[arg-type]
    Create = create_model(create_name or f"{document_model.__name__}Create", **ann_create)  # type: ignore[arg-type]
    Update = create_model(update_name or f"{document_model.__name__}Update", **ann_update)  # type: ignore[arg-type]

    for M in (Read, Create, Update):
        M.model_config = ConfigDict(from_attributes=True)
        M.model_rebuild()

    return Read, Create, Update
