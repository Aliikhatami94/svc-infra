from __future__ import annotations

from .models import APIVersionSpec, ServiceInfo, VersionInfo


def conventions_mutator():
    # Error Problem schema + reusable responses; set default servers only if missing
    from .conventions import PROBLEM_SCHEMA, STANDARD_RESPONSES

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {})
        schemas = comps.setdefault("schemas", {})
        responses = comps.setdefault("responses", {})
        schema.setdefault("servers", [{"url": "/"}])
        schemas.setdefault("Problem", PROBLEM_SCHEMA)
        for k, v in STANDARD_RESPONSES.items():
            responses.setdefault(k, v)
        return schema

    return m


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


def info_mutator(base: ServiceInfo, spec: APIVersionSpec | None):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        info = schema.setdefault("info", {})

        # Base defaults
        info.setdefault("title", base.name)
        info.setdefault("version", base.release)
        if base.description is not None:
            info["description"] = base.description
        if base.terms_of_service is not None:
            info["termsOfService"] = base.terms_of_service
        if base.contact:
            info["contact"] = base.contact.model_dump(exclude_none=True)
        if base.license:
            info["license"] = base.license.model_dump(exclude_none=True)

        # Per-version overrides
        vi: VersionInfo | None = spec.info if spec else None
        if vi:
            if vi.title is not None:
                info["title"] = vi.title
            if vi.version_label is not None:
                info["version"] = vi.version_label
            if vi.description is not None:
                info["description"] = vi.description
            if vi.terms_of_service is not None:
                info["termsOfService"] = vi.terms_of_service
            if vi.contact is not None:
                info["contact"] = vi.contact.model_dump(exclude_none=True)
            if vi.license is not None:
                info["license"] = vi.license.model_dump(exclude_none=True)
        return schema

    return m


def servers_mutator(url: str):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        schema["servers"] = [{"url": url}]
        return schema

    return m
