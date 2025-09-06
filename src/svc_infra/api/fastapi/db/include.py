from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Type

from fastapi import FastAPI

from svc_infra.api.fastapi.db.integration import SessionDep
from svc_infra.db.manage.repository import Repository
from svc_infra.db.manage.service import Service
from svc_infra.db.manage.router_plus import make_crud_router_plus
from svc_infra.db.manage.management import make_crud_schemas


@dataclass
class Resource:
    # Required
    model: type[object]
    prefix: str  # e.g. "/projects"

    # Optional FastAPI presentation
    tags: Optional[list[str]] = None

    # Optional overrides / knobs
    id_attr: str = "id"
    soft_delete: bool = False            # enables soft-delete endpoints if your model has deleted_at
    search_fields: Optional[list[str]] = None  # used by router_plus if implemented there
    ordering_default: Optional[str] = None
    allowed_order_fields: Optional[list[str]] = None  # expose to router

    # If you already have Pydantic classes, pass them here and we won't autogen
    read_schema: Optional[Type[Any]] = None
    create_schema: Optional[Type[Any]] = None
    update_schema: Optional[Type[Any]] = None

    # Autogen schema names (only used when the three above are None)
    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None

    # When autogenerating Create, exclude these model columns (e.g. "id", server defaults)
    create_exclude: tuple[str, ...] = ("id",)


def include_resources(app: FastAPI, resources: Sequence[Resource]) -> None:
    """
    Mounts CRUD (and extras) for each Resource by creating:
    Repository(model) -> Service(repo) -> router_plus(router with pagination/search/etc.)
    """
    for r in resources:
        # Repository + Service
        repo = Repository(model=r.model, id_attr=r.id_attr, soft_delete=r.soft_delete)
        svc = Service(repo)

        # Schemas: use provided, or autogenerate from the SQLAlchemy model
        if r.read_schema and r.create_schema and r.update_schema:
            Read, Create, Update = r.read_schema, r.create_schema, r.update_schema
        else:
            Read, Create, Update = make_crud_schemas(
                r.model,
                create_exclude=r.create_exclude,
                read_name=r.read_name,
                create_name=r.create_name,
                update_name=r.update_name,
            )

        # Router
        router = make_crud_router_plus(
            model=r.model,
            service=svc,
            read_schema=Read,
            create_schema=Create,
            update_schema=Update,
            prefix=r.prefix,
            tags=r.tags,
            search_fields=r.search_fields,
            default_ordering=r.ordering_default,
            allowed_order_fields=r.allowed_order_fields,
            session_dep=SessionDep,      # DI hook for DB session
            # Note: router_plus mounts under "/_db" by default. Override via mount_under_db_prefix=False if desired.
        )
        app.include_router(router)


__all__ = ["Resource", "include_resources"]