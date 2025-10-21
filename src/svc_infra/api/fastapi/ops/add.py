from __future__ import annotations

import os
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse


def add_probes(
    app: FastAPI,
    *,
    prefix: str = "/_ops",
    include_in_schema: bool = False,
) -> None:
    """Mount basic liveness/readiness/startup probes under prefix."""
    from svc_infra.api.fastapi.dual.public import public_router

    router = public_router(prefix=prefix, tags=["ops"], include_in_schema=include_in_schema)

    @router.get("/live")
    async def live() -> JSONResponse:  # noqa: D401, ANN201
        return JSONResponse({"status": "ok"})

    @router.get("/ready")
    async def ready() -> JSONResponse:  # noqa: D401, ANN201
        # In the future, add checks (DB ping, cache ping) via DI hooks.
        return JSONResponse({"status": "ok"})

    @router.get("/startup")
    async def startup_probe() -> JSONResponse:  # noqa: D401, ANN201
        return JSONResponse({"status": "ok"})

    app.include_router(router)


def add_maintenance_mode(
    app: FastAPI,
    *,
    env_var: str = "MAINTENANCE_MODE",
    exempt_prefixes: tuple[str, ...] | None = None,
) -> None:
    """Enable a simple maintenance gate controlled by an env var.

    When MAINTENANCE_MODE is truthy, all non-GET requests return 503.
    """

    @app.middleware("http")
    async def _maintenance_gate(request: Request, call_next):  # noqa: ANN001, ANN202
        flag = str(os.getenv(env_var, "")).lower() in {"1", "true", "yes", "on"}
        if flag and request.method not in {"GET", "HEAD", "OPTIONS"}:
            path = request.scope.get("path", "")
            if exempt_prefixes and any(path.startswith(p) for p in exempt_prefixes):
                return await call_next(request)
            return JSONResponse({"detail": "maintenance"}, status_code=503)
        return await call_next(request)


def circuit_breaker_dependency(limit: int = 100, window_seconds: int = 60) -> Callable:
    """Return a dependency that can trip rejective errors based on external metrics.

    This is a placeholder; callers can swap with a provider that tracks failures and opens the
    breaker. Here, we read an env var to simulate an open breaker.
    """

    async def _dep(_: Request) -> None:  # noqa: D401, ANN202
        if str(os.getenv("CIRCUIT_OPEN", "")).lower() in {"1", "true", "yes", "on"}:
            raise HTTPException(status_code=503, detail="circuit open")

    return _dep


__all__ = ["add_probes", "add_maintenance_mode", "circuit_breaker_dependency"]
