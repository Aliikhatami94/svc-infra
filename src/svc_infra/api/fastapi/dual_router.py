from __future__ import annotations

from typing import Any, Callable, List, Sequence

from fastapi import APIRouter
from fastapi.routing import APIRoute


def _norm_primary(path: str) -> str:
    """
    Prefer the no-trailing-slash version in docs.
    Special-case "/" so it remains "/" (not empty).
    """
    if not path:
        return "/"
    if path == "/":
        return "/"
    return path[:-1] if path.endswith("/") else path


def _alt_with_slash(path: str) -> str:
    """
    Ensure the alternate has a trailing slash (except root which already has one).
    """
    if not path:
        return "/"
    if path.endswith("/"):
        return path
    return path + "/"


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


# --------- Migration helper: convert an existing APIRouter to DualAPIRouter ---------


def dualize_router(src: APIRouter, *, show_in_schema: bool = True) -> DualAPIRouter:
    """
    Create a DualAPIRouter and re-register all routes from `src` with trailing-slash twins.
    - Preserves route metadata (responses, tags, name, status_code, dependencies, etc).
    - Skips exact duplicates.
    Note: WebSocket routes cannot be distinguished via APIRoute; re-add those manually if needed.
    """
    dst = DualAPIRouter(
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
        # FastAPI/Starlette ignore unknown kwargs gracefully across versions
    )

    # Copy each APIRoute
    for r in src.routes:
        if not isinstance(r, APIRoute):
            # Skip WebSockets here; add them manually with dst.websocket(...)
            continue

        # Gather the registration args
        methods: Sequence[str] = sorted(r.methods or [])
        path: str = r.path
        endpoint: Callable[..., Any] = r.endpoint

        dst.add_api_route(  # primary
            _norm_primary(path),
            endpoint,
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

        alt = _alt_with_slash(path)
        if alt != _norm_primary(path):
            dst.add_api_route(  # hidden twin
                alt,
                endpoint,
                methods=list(methods),
                response_model=r.response_model,
                status_code=r.status_code,
                tags=r.tags,
                dependencies=r.dependencies,
                summary=r.summary,
                description=r.description,
                responses=r.responses,
                deprecated=r.deprecated,
                name=r.name,  # name reuse is OK; path differs
                operation_id=None,  # keep it out of schema anyway
                response_class=r.response_class,
                response_description=r.response_description,
                callbacks=r.callbacks,
                openapi_extra=r.openapi_extra,
                include_in_schema=False,
            )

    return dst


__all__ = ["DualAPIRouter", "dualize_router"]
