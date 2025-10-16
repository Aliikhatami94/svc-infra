from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI


def add_docs(
    app: FastAPI,
    *,
    redoc_url: str = "/redoc",
    swagger_url: str = "/docs",
    openapi_url: str = "/openapi.json",
    export_openapi_to: Optional[str] = None,
) -> None:
    """Enable docs endpoints and optionally export OpenAPI schema to disk on startup."""
    # Configure FastAPI docs URLs
    app.docs_url = swagger_url
    app.redoc_url = redoc_url
    app.openapi_url = openapi_url

    if export_openapi_to:
        export_path = Path(export_openapi_to)

        @app.on_event("startup")
        async def _export_spec() -> None:  # noqa: ANN202
            spec = app.openapi()
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(spec, indent=2))


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
