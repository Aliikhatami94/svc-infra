from __future__ import annotations

from typing import List, Tuple

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

# Registry so the landing page can show nice cards.
DOC_SCOPES: List[Tuple[str, str, str, str, str]] = []
# (prefix, swagger_path, redoc_path, openapi_path, title)


def add_prefixed_docs(app: FastAPI, *, prefix: str, title: str) -> None:
    """
    Exposes filtered OpenAPI + Swagger/ReDoc for only the routes under `prefix`.
    - OpenAPI:  {prefix}/openapi.json
    - Swagger:  {prefix}/docs
    - ReDoc:    {prefix}/redoc
    """
    scope = prefix.rstrip("/") or "/"
    openapi_path = f"{scope}/openapi.json"
    swagger_path = f"{scope}/docs"
    redoc_path = f"{scope}/redoc"

    def _build_filtered_schema():
        full = app.openapi()  # already mutated by your pipeline
        paths = full.get("paths", {})
        filtered = {p: v for (p, v) in paths.items() if p == scope or p.startswith(scope + "/")}
        # shallow copy, keep components/security/etc. intact
        schema = dict(full)
        info = dict(schema.get("info", {}))
        info["title"] = f'{info.get("title", "API")} • {title}'
        schema["info"] = info
        schema["paths"] = filtered
        # Optional: set servers so try-it-out uses the right base (not required)
        # schema["servers"] = [{"url": ""}]  # leave empty so it uses current origin
        return schema

    @app.get(openapi_path, include_in_schema=False)
    def scoped_openapi():
        return _build_filtered_schema()

    @app.get(swagger_path, include_in_schema=False)
    def scoped_swagger():
        return get_swagger_ui_html(openapi_url=openapi_path, title=f"{title} • Swagger")

    @app.get(redoc_path, include_in_schema=False)
    def scoped_redoc():
        return get_redoc_html(openapi_url=openapi_path, title=f"{title} • ReDoc")

    DOC_SCOPES.append((scope, swagger_path, redoc_path, openapi_path, title))
