from __future__ import annotations

from typing import Any, Callable, List, Sequence

from fastapi import APIRouter
from fastapi.routing import APIRoute

from svc_infra.api.fastapi import public_router
from svc_infra.api.fastapi.auth import protected_router, service_router, user_router


def _norm_primary(path: str) -> str:
    if not path or path == "/":
        return "/"
    return path[:-1] if path.endswith("/") else path


def _alt_with_slash(path: str) -> str:
    if not path:
        return "/"
    return path if path.endswith("/") else path + "/"


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


class DualAPIRouter(APIRouter):
    """
    Registers two routes per endpoint:
      • primary: shown in OpenAPI (no trailing slash)
      • alternate: hidden in OpenAPI (with trailing slash)
    Keeps redirect_slashes=False behavior (no 307s).
    """

    def __init__(self, *args, redirect_slashes: bool = False, **kwargs) -> None:
        # Force no implicit 307s; we explicitly add a twin instead.
        super().__init__(*args, redirect_slashes=redirect_slashes, **kwargs)

    # ---------- core helper ----------

    def _dual_decorator(
        self,
        path: str,
        methods: List[str],
        *,
        show_in_schema: bool = True,
        **kwargs: Any,
    ):
        # Special-case the router root: "", "/" → register both "" and "/"
        is_rootish = path in {"", "/"}
        primary = _norm_primary(path or "")
        alt = _alt_with_slash(path or "")

        def decorator(func: Callable[..., Any]):
            if is_rootish:
                # /prefix  (no trailing slash)
                self.add_api_route(
                    "", func, methods=methods, include_in_schema=show_in_schema, **kwargs
                )
                # /prefix/ (with trailing slash; hidden)
                self.add_api_route("/", func, methods=methods, include_in_schema=False, **kwargs)
                return func

            # Normal case: visible primary (no slash in docs) + hidden twin (with slash)
            self.add_api_route(
                primary, func, methods=methods, include_in_schema=show_in_schema, **kwargs
            )
            if alt != primary:
                self.add_api_route(alt, func, methods=methods, include_in_schema=False, **kwargs)
            return func

        return decorator

    # ---------- HTTP method shorthands ----------

    def get(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["GET"], show_in_schema=show_in_schema, **kwargs)

    def post(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["POST"], show_in_schema=show_in_schema, **kwargs)

    def patch(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["PATCH"], show_in_schema=show_in_schema, **kwargs)

    def delete(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["DELETE"], show_in_schema=show_in_schema, **kwargs)

    def put(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["PUT"], show_in_schema=show_in_schema, **kwargs)

    def options(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["OPTIONS"], show_in_schema=show_in_schema, **kwargs)

    def head(self, path: str, *_, show_in_schema: bool = True, **kwargs: Any):
        return self._dual_decorator(path, ["HEAD"], show_in_schema=show_in_schema, **kwargs)

    # ---------- WebSocket ----------

    def websocket(self, path: str, *_, **kwargs: Any):
        """
        Dual-registrations for WebSockets. Starlette doesn't expose OpenAPI for WS,
        so there is no schema visibility knob here.
        """
        primary = _norm_primary(path or "")
        alt = _alt_with_slash(path or "")

        def decorator(func: Callable[..., Any]):
            # Signature must accept (websocket: WebSocket, ...)
            if "dependencies" in kwargs:
                # FastAPI's add_api_websocket_route also accepts dependencies, tags, name, etc.
                self.add_api_websocket_route(primary, func, **kwargs)
                if alt != primary:
                    self.add_api_websocket_route(alt, func, **kwargs)
            else:
                self.add_api_websocket_route(primary, func, **kwargs)
                if alt != primary:
                    self.add_api_websocket_route(alt, func, **kwargs)
            return func

        return decorator


__all__ = [
    "DualAPIRouter",
    "dualize_public",
    "dualize_user",
    "dualize_protected",
    "dualize_service",
]
