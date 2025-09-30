from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

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
