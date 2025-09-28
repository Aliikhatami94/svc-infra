from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _normalize_security_list(sec: list | None, *, drop_schemes: set[str] = None) -> list:
    """Deduplicate and optionally drop auth schemes in a `security` list."""
    if not sec:
        return []

    drop_schemes = drop_schemes or set()

    # 1) Remove unwanted schemes inside each dict (dict = AND of schemes)
    cleaned = []
    for item in sec:
        if not isinstance(item, dict):
            continue
        kept = {k: v for k, v in item.items() if k not in drop_schemes}
        if kept:
            cleaned.append(kept)

    # 2) Deduplicate exact dicts (keep first occurrence)
    seen_dicts = set()
    unique = []
    for item in cleaned:
        # canonicalize dict so it’s hashable
        canon = tuple(sorted((k, tuple(v or [])) for k, v in item.items()))
        if canon in seen_dicts:
            continue
        seen_dicts.add(canon)
        unique.append(item)

    # 3) If callers used one-scheme-per-dict (common), also dedupe by scheme name
    #    e.g. [{"OAuth2PasswordBearer":[]}, {"OAuth2PasswordBearer":[]}] -> one entry
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
    def _openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})

        comps.setdefault(
            "OAuth2PasswordBearer",
            {"type": "oauth2", "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}}},
        )
        if include_api_key:
            comps.setdefault(
                "APIKeyHeader", {"type": "apiKey", "name": "X-API-Key", "in": "header"}
            )

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
