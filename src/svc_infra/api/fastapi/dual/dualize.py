from __future__ import annotations

from typing import Callable

from fastapi import APIRouter

from .protected import protected_router, service_router, user_router
from .public import public_router
from .router import DualAPIRouter


def dualize_into(
    src: APIRouter, dst_factory: Callable[..., DualAPIRouter], *, show_in_schema=True
) -> DualAPIRouter:
    """
    Clone `src` into a DualAPIRouter without re-parsing the primary endpoints.

    Strategy:
      1) Create an empty DualAPIRouter (prefix="").
      2) Include the original router `src` so the *original* APIRoute objects
         (and their already-resolved request models) are used and shown in OpenAPI.
      3) Add *hidden* trailing-slash twins that point to the same endpoint callables.
         These don’t show in OpenAPI, so re-parsing them is harmless.
    """
    # IMPORTANT: make a fresh router with NO prefix; we will include `src` with its own prefix.
    dst = dst_factory(
        prefix="",  # prevent double-prefixing on include_router
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

    # 1) Keep original routes *intact* (OpenAPI stays correct).
    #    We pass prefix=src.prefix so paths remain the same.
    dst.include_router(
        src,
        prefix=src.prefix,
        tags=src.tags,
        include_in_schema=show_in_schema,
    )

    # 2) Add hidden trailing-slash twins (no OpenAPI).
    from fastapi.routing import APIRoute

    from .utils import _alt_with_slash, _norm_primary

    for r in src.routes:
        if not isinstance(r, APIRoute):
            continue

        methods = sorted(r.methods or [])
        primary = _norm_primary(r.path)
        alt = _alt_with_slash(r.path)

        if alt == primary:
            continue

        # Build full path using the same prefix we used for include_router
        alt_full = f"{src.prefix}{alt}"

        # Add a hidden twin. Re-parsing here is okay because this route is not in the schema.
        dst.add_api_route(
            alt_full,
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
