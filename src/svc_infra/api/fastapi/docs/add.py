from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from .landing import CardSpec, DocTargets, render_index_html
from .scoped import DOC_SCOPES


def add_docs(
    app: FastAPI,
    *,
    redoc_url: str = "/redoc",
    swagger_url: str = "/docs",
    openapi_url: str = "/openapi.json",
    export_openapi_to: Optional[str] = None,
    # Landing page options
    landing_url: str = "/",
    include_landing: bool = True,
) -> None:
    """Enable docs endpoints and optionally export OpenAPI schema to disk on startup.

    We mount docs and OpenAPI routes explicitly so this works even when configured post-init.
    """

    # OpenAPI JSON route
    async def openapi_handler() -> JSONResponse:  # noqa: ANN201
        return JSONResponse(app.openapi())

    app.add_api_route(openapi_url, openapi_handler, methods=["GET"], include_in_schema=False)

    # Swagger UI route
    async def swagger_ui(request: Request) -> HTMLResponse:  # noqa: ANN201
        resp = get_swagger_ui_html(openapi_url=openapi_url, title="API Docs")
        theme = request.query_params.get("theme")
        if theme == "dark":
            return _with_dark_mode(resp)
        return resp

    app.add_api_route(swagger_url, swagger_ui, methods=["GET"], include_in_schema=False)

    # Redoc route
    async def redoc_ui(request: Request) -> HTMLResponse:  # noqa: ANN201
        resp = get_redoc_html(openapi_url=openapi_url, title="API ReDoc")
        theme = request.query_params.get("theme")
        if theme == "dark":
            return _with_dark_mode(resp)
        return resp

    app.add_api_route(redoc_url, redoc_ui, methods=["GET"], include_in_schema=False)

    # Optional export to disk on startup
    if export_openapi_to:
        export_path = Path(export_openapi_to)

        async def _export_docs() -> None:
            # Startup export
            spec = app.openapi()
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(spec, indent=2))

        app.add_event_handler("startup", _export_docs)

    # Optional landing page with the same look/feel as setup_service_api
    if include_landing:
        # Avoid path collision; if landing_url is already taken for GET, fallback to "/_docs"
        existing_paths = {
            (getattr(r, "path", None) or getattr(r, "path_format", None))
            for r in getattr(app, "routes", [])
            if getattr(r, "methods", None) and "GET" in r.methods
        }
        landing_path = landing_url or "/"
        if landing_path in existing_paths:
            landing_path = "/_docs"

        async def _landing() -> HTMLResponse:  # noqa: ANN201
            cards: list[CardSpec] = []
            # Root docs card using the provided paths
            cards.append(
                CardSpec(
                    tag="",
                    docs=DocTargets(swagger=swagger_url, redoc=redoc_url, openapi_json=openapi_url),
                )
            )
            # Scoped docs (if any were registered via add_prefixed_docs)
            for scope, swagger, redoc, openapi_json, _title in DOC_SCOPES:
                cards.append(
                    CardSpec(
                        tag=scope.strip("/"),
                        docs=DocTargets(swagger=swagger, redoc=redoc, openapi_json=openapi_json),
                    )
                )
            html = render_index_html(
                service_name=app.title or "API", release=app.version or "", cards=cards
            )
            return HTMLResponse(html)

        app.add_api_route(landing_path, _landing, methods=["GET"], include_in_schema=False)


def _with_dark_mode(resp: HTMLResponse) -> HTMLResponse:
    """Return a copy of the HTMLResponse with a minimal dark-theme CSS injected.

    We avoid depending on custom Swagger/ReDoc builds; this works by inlining a small CSS
    block and toggling a `.dark` class on the body element.
    """
    try:
        body = resp.body.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover - very unlikely
        return resp

    css = _DARK_CSS
    if "</head>" in body:
        body = body.replace("</head>", f"<style>\n{css}\n</style></head>", 1)
    # add class to body to allow stronger selectors
    body = body.replace("<body>", '<body class="dark">', 1)
    return HTMLResponse(content=body, status_code=resp.status_code, headers=dict(resp.headers))


_DARK_CSS = """
/* Minimal dark mode override for Swagger/ReDoc */
@media (prefers-color-scheme: dark) { :root { color-scheme: dark; } }
html.dark, body.dark { background: #0b0e14; color: #e0e6f1; }
#swagger, .redoc-wrap { background: transparent; }
a { color: #62aef7; }
"""


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
