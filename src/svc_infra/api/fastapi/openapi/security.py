from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _normalize_security_list(sec: list | None, *, drop_schemes: set[str] = None) -> list:
    if not sec:
        return []
    drop_schemes = drop_schemes or set()
    cleaned = []
    for item in sec:
        if not isinstance(item, dict):
            continue
        kept = {k: v for k, v in item.items() if k not in drop_schemes}
        if kept:
            cleaned.append(kept)
    # dedupe exact dicts
    seen_dicts = set()
    unique = []
    for item in cleaned:
        canon = tuple(sorted((k, tuple(v or [])) for k, v in item.items()))
        if canon in seen_dicts:
            continue
        seen_dicts.add(canon)
        unique.append(item)
    # dedupe single-scheme repeats
    seen_schemes = set()
    final = []
    for item in unique:
        if len(item) == 1:
            scheme = next(iter(item))
            if scheme in seen_schemes:
                continue
            seen_schemes.add(scheme)
        final.append(item)
    return final


def install_openapi_auth(app: FastAPI, *, include_api_key: bool = False) -> None:
    previous = getattr(app, "openapi", None)

    def _openapi():
        # Chain prior customizer if any
        base_schema = (
            previous()
            if callable(previous)
            else get_openapi(title=app.title, version=app.version, routes=app.routes)
        )

        schema = dict(base_schema)
        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        comps.setdefault(
            "OAuth2PasswordBearer",
            {"type": "oauth2", "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}}},
        )
        if include_api_key:
            comps.setdefault(
                "APIKeyHeader", {"type": "apiKey", "name": "X-API-Key", "in": "header"}
            )

        # Drop SessionCookie references from ops and dedupe
        drop = {"SessionCookie"}
        for path_item in (schema.get("paths") or {}).values():
            for method_obj in path_item.values():
                if isinstance(method_obj, dict):
                    method_obj["security"] = _normalize_security_list(
                        method_obj.get("security"), drop_schemes=drop
                    )

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
