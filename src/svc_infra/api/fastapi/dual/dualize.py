from __future__ import annotations

from typing import Callable, Sequence

from fastapi import APIRouter
from fastapi.routing import APIRoute

from .protected import protected_router, service_router, user_router
from .public import public_router
from .router import DualAPIRouter
from .utils import _alt_with_slash, _norm_primary


def dualize_into(
    src: APIRouter, dst_factory: Callable[..., DualAPIRouter], *, show_in_schema=True
) -> DualAPIRouter:
    """Clone routes from an APIRouter into a new DualAPIRouter created by `dst_factory`."""
    dst = dst_factory(
        prefix=src.prefix,
        tags=list(src.tags or []),
        dependencies=list(src.dependencies or []),
        default_response_class=src.default_response_class,  # type: ignore[arg-type]
        responses=dict(src.responses or {}),
        callbacks=list(src.callbacks or []),
        routes=[],  # start empty
        redirect_slashes=False,
        default=src.default,
        on_startup=list(src.on_startup),
        on_shutdown=list(src.on_shutdown),
    )

    for r in src.routes:
        if not isinstance(r, APIRoute):
            continue

        methods: Sequence[str] = sorted(r.methods or [])
        primary = _norm_primary(r.path)
        alt = _alt_with_slash(r.path)

        # visible primary (no trailing slash)
        dst.add_api_route(
            primary,
            r.endpoint,
            methods=list(methods),
            response_model=r.response_model,
            status_code=r.status_code,
            tags=r.tags,
            dependencies=r.dependencies,
            summary=r.summary,
            description=r.description,
            responses=r.responses,
            deprecated=r.deprecated,
            name=r.name,
            operation_id=r.operation_id,
            response_class=r.response_class,
            response_description=r.response_description,
            callbacks=r.callbacks,
            openapi_extra=r.openapi_extra,
            include_in_schema=show_in_schema,
        )

        # hidden twin (with trailing slash)
        if alt != primary:
            dst.add_api_route(
                alt,
                r.endpoint,
                methods=list(methods),
                response_model=r.response_model,
                status_code=r.status_code,
                tags=r.tags,
                dependencies=r.dependencies,
                summary=r.summary,
                description=r.description,
                responses=r.responses,
                deprecated=r.deprecated,
                name=r.name,
                operation_id=None,
                response_class=r.response_class,
                response_description=r.response_description,
                callbacks=r.callbacks,
                openapi_extra=r.openapi_extra,
                include_in_schema=False,
            )

    return dst


# Convenience shorthands (read nicely at callsites)
def dualize_public(src: APIRouter, *, show_in_schema=True) -> DualAPIRouter:
    return dualize_into(src, public_router, show_in_schema=show_in_schema)


def dualize_user(src: APIRouter, *, show_in_schema=True) -> DualAPIRouter:
    return dualize_into(src, user_router, show_in_schema=show_in_schema)


def dualize_protected(src: APIRouter, *, show_in_schema=True) -> DualAPIRouter:
    return dualize_into(src, protected_router, show_in_schema=show_in_schema)


def dualize_service(src: APIRouter, *, show_in_schema=True) -> DualAPIRouter:
    return dualize_into(src, service_router, show_in_schema=show_in_schema)


__all__ = [
    "dualize_public",
    "dualize_user",
    "dualize_protected",
    "dualize_service",
]
