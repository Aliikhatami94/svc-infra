from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, create_model


@dataclass(frozen=True)
class FieldSpec:
    """
    Generic description of a field we want to expose in CRUD schemas.

    name: field name
    typ: the Python type (e.g., str, int, datetime, custom types)
    required_for_create: if True -> required in Create schema
    exclude_from_create: if True -> omitted from Create schema
    exclude_from_read: if True -> omitted from Read schema
    exclude_from_update: if True -> omitted from Update schema
    """

    name: str
    typ: type[Any]
    required_for_create: bool
    exclude_from_create: bool = False
    exclude_from_read: bool = False
    exclude_from_update: bool = False


def _opt(t: type[Any]) -> tuple[Any, Any]:
    # convenience: Optional[t] with default None
    return (t | None, None)


def make_crud_schemas_from_specs(
    *,
    specs: Sequence[FieldSpec],
    read_name: str | None,
    create_name: str | None,
    update_name: str | None,
    json_encoders: dict[type[Any], Any] | None = None,
) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    ann_read: dict[str, tuple[Any, Any]] = {}
    ann_create: dict[str, tuple[Any, Any]] = {}
    ann_update: dict[str, tuple[Any, Any]] = {}

    for s in specs:
        # READ: include unless excluded; all fields Optional
        if not s.exclude_from_read:
            ann_read[s.name] = _opt(s.typ)

        # CREATE: include unless excluded; required if required_for_create
        if not s.exclude_from_create:
            if s.required_for_create:
                ann_create[s.name] = (s.typ, ...)
            else:
                ann_create[s.name] = (s.typ, None)

        # UPDATE: include unless excluded; always Optional
        if not s.exclude_from_update:
            ann_update[s.name] = _opt(s.typ)

    Read = create_model(read_name or "Read", **cast("dict[str, Any]", ann_read))
    Create = create_model(create_name or "Create", **cast("dict[str, Any]", ann_create))
    Update = create_model(update_name or "Update", **cast("dict[str, Any]", ann_update))

    cfg = ConfigDict(from_attributes=True)
    if json_encoders:
        cfg = ConfigDict(from_attributes=True, json_encoders=json_encoders)

    for M in (Read, Create, Update):
        M.model_config = cfg
        M.model_rebuild()

    return Read, Create, Update
