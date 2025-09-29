from __future__ import annotations

from fastapi import FastAPI

from svc_infra.api.fastapi.openapi.apply import chain_openapi


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


def auth_mutator(include_api_key: bool):
    def _m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        comps.setdefault(
            "OAuth2PasswordBearer",
            {"type": "oauth2", "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}}},
        )
        if include_api_key:
            comps.setdefault(
                "APIKeyHeader", {"type": "apiKey", "name": "X-API-Key", "in": "header"}
            )

        # Drop SessionCookie and dedupe per-op security
        def _normalize_security_list(sec: list | None, drop: set[str]) -> list:
            if not sec:
                return []
            cleaned = []
            for item in sec:
                if isinstance(item, dict):
                    kept = {k: v for k, v in item.items() if k not in drop}
                    if kept:
                        cleaned.append(kept)
            # dedupe dicts
            seen = set()
            out = []
            for d in cleaned:
                key = tuple(sorted((k, tuple(v or [])) for k, v in d.items()))
                if key in seen:
                    continue
                seen.add(key)
                out.append(d)
            # dedupe single-scheme repeats
            seen_schemes = set()
            final = []
            for d in out:
                if len(d) == 1:
                    k = next(iter(d))
                    if k in seen_schemes:
                        continue
                    seen_schemes.add(k)
                final.append(d)
            return final

        drop = {"SessionCookie"}
        for path in (schema.get("paths") or {}).values():
            for method_obj in path.values():
                if isinstance(method_obj, dict):
                    method_obj["security"] = _normalize_security_list(
                        method_obj.get("security"), drop
                    )

        return schema

    return _m


def install_openapi_auth(app: FastAPI, *, include_api_key: bool = False) -> None:
    chain_openapi(app, auth_mutator(include_api_key))
