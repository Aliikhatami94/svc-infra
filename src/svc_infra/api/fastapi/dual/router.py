from __future__ import annotations

from typing import Any, Callable, Type

from fastapi import APIRouter
from fastapi.params import Depends
from pydantic import BaseModel

from ..pagination import Paginated, make_pagination_injector
from .utils import _alt_with_slash, _norm_primary


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
        self, path: str, methods: list[str], *, show_in_schema: bool = True, **kwargs
    ):
        is_rootish = path in {"", "/"}
        primary = _norm_primary(path or "")
        alt = _alt_with_slash(path or "")

        safe_methods = {"GET", "HEAD", "OPTIONS"}

        def decorator(func):
            if is_rootish:
                # primary root
                self.add_api_route(
                    "", func, methods=methods, include_in_schema=show_in_schema, **kwargs
                )
                # only add the "/" twin for *safe* methods
                if set(m.upper() for m in methods) <= safe_methods:
                    self.add_api_route(
                        "/", func, methods=methods, include_in_schema=False, **kwargs
                    )
                return func

            # non-root unchanged
            self.add_api_route(
                primary, func, methods=methods, include_in_schema=show_in_schema, **kwargs
            )
            if alt != primary:
                self.add_api_route(alt, func, methods=methods, include_in_schema=False, **kwargs)
            return func

        return decorator

    def add_api_route(self, path, endpoint, **kwargs):
        methods = set((kwargs.get("methods") or []))
        for r in self.routes:
            if getattr(r, "path", None) == path and methods & (
                getattr(r, "methods", set()) or set()
            ):
                raise RuntimeError(f"Duplicate route in router: {methods} {path}")
        return super().add_api_route(path, endpoint, **kwargs)

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

    def list(
        self,
        path: str,
        *,
        model: Type[BaseModel],
        envelope: bool = False,
        cursor: bool = True,
        page: bool = True,
        default_limit: int = 50,
        max_limit: int = 200,
        show_in_schema: bool = True,
        **kwargs: Any,
    ):
        """
        Sugar for list endpoints.

        - Auto-inject pagination/filter context (no Depends in your signature).
        - Auto-picks response_model: list[model] or Paginated[model].
        - Works with your OpenAPI mutators which already attach the shared params.
        - Per-route opt-out of OpenAPI param auto-attach: openapi_extra={"x_no_auto_pagination": True}
        """
        # pick response model
        if envelope:
            response_model = Paginated[model]  # type: ignore[index]
        else:
            response_model = list[model]  # type: ignore[index]

        injector = make_pagination_injector(
            envelope=envelope,
            allow_cursor=cursor,
            allow_page=page,
            default_limit=default_limit,
            max_limit=max_limit,
        )

        # ensure our injector runs; don't mutate caller's dependencies
        deps = list(kwargs.get("dependencies") or [])
        deps.append(Depends(injector))
        kwargs["dependencies"] = deps
        kwargs["response_model"] = kwargs.get("response_model") or response_model

        # we still want the dual-registration behavior
        return self._dual_decorator(path, ["GET"], show_in_schema=show_in_schema, **kwargs)

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
