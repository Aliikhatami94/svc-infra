from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse


def add_docs(
    app: FastAPI,
    *,
    redoc_url: str = "/redoc",
    swagger_url: str = "/docs",
    openapi_url: str = "/openapi.json",
    export_openapi_to: Optional[str] = None,
) -> None:
    """Enable docs endpoints and optionally export OpenAPI schema to disk on startup.

    We mount docs and OpenAPI routes explicitly so this works even when configured post-init.
    """

    # OpenAPI JSON route
    async def openapi_handler() -> JSONResponse:  # noqa: ANN201
        return JSONResponse(app.openapi())

    app.add_api_route(openapi_url, openapi_handler, methods=["GET"], include_in_schema=False)

    # Swagger UI route
    async def swagger_ui() -> HTMLResponse:  # noqa: ANN201
        return get_swagger_ui_html(openapi_url=openapi_url, title="API Docs")

    app.add_api_route(swagger_url, swagger_ui, methods=["GET"], include_in_schema=False)

    # Redoc route
    async def redoc_ui() -> HTMLResponse:  # noqa: ANN201
        return get_redoc_html(openapi_url=openapi_url, title="API ReDoc")

    app.add_api_route(redoc_url, redoc_ui, methods=["GET"], include_in_schema=False)

    # Optional export to disk on startup
    if export_openapi_to:
        export_path = Path(export_openapi_to)

        @asynccontextmanager
        async def _docs_ctx(app_: FastAPI):  # noqa: ANN001
            # Startup export
            spec = app.openapi()
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(spec, indent=2))
            try:
                yield
            finally:
                pass

        # Install/override lifespan handler for this app if not already set by caller.
        app.router.lifespan_context = _docs_ctx  # type: ignore[assignment]


def add_sdk_generation_stub(
    app: FastAPI,
    *,
    on_generate: Optional[callable] = None,
    openapi_path: str = "/openapi.json",
) -> None:
    """Hook to add an SDK generation stub.

    Provide `on_generate()` to run generation (e.g., openapi-generator). This is a stub only; we
    don't ship a hard dependency. If `on_generate` is provided, we expose `/_docs/generate-sdk`.
    """
    from svc_infra.api.fastapi.dual.public import public_router

    if not on_generate:
        return

    router = public_router(prefix="/_docs", include_in_schema=False)

    @router.post("/generate-sdk")
    async def _generate() -> dict:  # noqa: ANN201
        on_generate()
        return {"status": "ok"}

    app.include_router(router)


__all__ = ["add_docs", "add_sdk_generation_stub"]
