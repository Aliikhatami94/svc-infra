from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Type
from fastapi import FastAPI
from .schemas import make_crud_schemas
from .router import make_crud_router

@dataclass
class Resources:
    model: Type[Any]
    prefix: str                    # e.g. "/projects"
    tags: Optional[list[str]] = None
    id_attr: str = "id"
    create_exclude: tuple[str, ...] = ("id",)
    update_optional: Optional[tuple[str, ...]] = None  # not used in simple generator above, kept for API parity
    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None

def include_crud(app: FastAPI, resources: Sequence[Resources]) -> None:
    for res in resources:
        Read, Create, Update = make_crud_schemas(
            res.model,
            create_exclude=res.create_exclude,
            update_optional=res.update_optional,
            read_name=res.read_name,
            create_name=res.create_name,
            update_name=res.update_name,
        )
        router = make_crud_router(
            model=res.model,
            read_schema=Read,
            create_schema=Create,
            update_schema=Update,
            prefix=res.prefix,
            tags=res.tags,
            id_attr=res.id_attr,
        )
        app.include_router(router)