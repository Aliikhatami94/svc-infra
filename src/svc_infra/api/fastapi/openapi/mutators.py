from __future__ import annotations

from typing import Dict, Iterable, Iterator, Tuple

from .models import APIVersionSpec, ServiceInfo, VersionInfo

# ------- small shared helpers -------

_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _iter_operations(schema: dict) -> Iterator[Tuple[str, str, dict]]:
    """Yield (path, method, op) for each operation object."""
    paths = schema.get("paths") or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() in _HTTP_METHODS and isinstance(op, dict):
                yield path, method.lower(), op


# ------- conventions / seeds -------


def conventions_mutator():
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


#  ----- problem+json / RFC 7807 -------


def normalize_problem_and_examples_mutator():
    """
    1) Force components.schemas.Problem.properties.instance.format = "uri-reference".
    2) Walk all responses content for application/problem+json and ensure example "instance" is absolute.
       If you prefer to keep uri-reference, this also allows relative. Pick ONE:
       - Either keep schema as 'uri-reference' (more permissive, allows relative + absolute)
       - Or keep schema as 'uri' and make all examples absolute.
    """
    ABSOLUTE_INSTANCE = "https://api.example.com/request/abc123"

    def _patch_example_val(val: dict):
        if not isinstance(val, dict):
            return
        inst = val.get("instance")
        if isinstance(inst, str) and (inst.startswith("/") or inst.startswith("about:")):
            # make absolute to satisfy format: uri
            val["instance"] = ABSOLUTE_INSTANCE

    def _walk_examples(node: dict):
        if not isinstance(node, dict):
            return
        content = node.get("content")
        if isinstance(content, dict):
            prob = content.get("application/problem+json")
            if isinstance(prob, dict):
                examples = prob.get("examples")
                if isinstance(examples, dict):
                    for ex in examples.values():
                        if isinstance(ex, dict):
                            val = ex.get("value")
                            if isinstance(val, dict):
                                _patch_example_val(val)

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {})
        # 1) Force Problem.instance to uri-reference (wins even if it exists)
        p = comps.setdefault("schemas", {}).get("Problem")
        if isinstance(p, dict):
            props = p.setdefault("properties", {})
            inst = props.setdefault("instance", {})
            inst["type"] = "string"
            inst["format"] = "uri-reference"  # <-- key bit
            inst.setdefault("description", "URI reference for this occurrence")
        else:
            # If somehow missing, inject your canonical Problem
            from .conventions import PROBLEM_SCHEMA

            comps.setdefault("schemas", {})["Problem"] = PROBLEM_SCHEMA

        # 2) Fix all examples under components.responses
        responses = comps.get("responses") or {}
        for r in responses.values():
            if isinstance(r, dict):
                _walk_examples(r)

        # 3) Fix inline responses under paths
        for path_item in (schema.get("paths") or {}).values():
            if not isinstance(path_item, dict):
                continue
            for op in path_item.values():
                if not isinstance(op, dict):
                    continue
                resps = op.get("responses")
                if not isinstance(resps, dict):
                    continue
                for r in resps.values():
                    if isinstance(r, dict):
                        _walk_examples(r)

        return schema

    return m


# ------- auth / security -------


def auth_mutator(include_api_key: bool):
    def _normalize_security_list(sec: list | None, drop: set[str]) -> list:
        if not sec:
            return []
        cleaned = []
        for item in sec:
            if isinstance(item, dict):
                kept = {k: v for k, v in item.items() if k not in drop}
                if kept:
                    cleaned.append(kept)
        # dedupe exact dicts
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

        drop = {"SessionCookie"}
        for _, _, op in _iter_operations(schema):
            op["security"] = _normalize_security_list(op.get("security"), drop)

        return schema

    return _m


# ------- info layering -------


def info_mutator(base: ServiceInfo, spec: APIVersionSpec | None):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        info = schema.setdefault("info", {})
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


# ------- servers -------


def servers_mutator(url: str):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        schema["servers"] = [{"url": url}]
        return schema

    return m


# ------- spectral helpers -------


def ensure_operation_descriptions_mutator(template: str = "{method} {path}."):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, method, op in _iter_operations(schema):
            desc = op.get("description")
            if not isinstance(desc, str) or not desc.strip():
                op["description"] = template.format(method=method.upper(), path=path)
        return schema

    return m


def ensure_global_tags_mutator(default_desc: str = "Operations related to {tag}."):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        used: set[str] = set()
        for _, _, op in _iter_operations(schema):
            for t in op.get("tags") or []:
                if isinstance(t, str):
                    used.add(t)

        existing = [t for t in (schema.get("tags") or []) if isinstance(t, dict) and "name" in t]
        names = {t["name"] for t in existing}
        for t in sorted(used):
            if t not in names:
                existing.append({"name": t, "description": default_desc.format(tag=t)})
        if existing:
            # keep alphabetical to satisfy Spectral’s alphabetical rule even after merges
            schema["tags"] = sorted(existing, key=lambda x: x.get("name", ""))
        return schema

    return m


def attach_standard_responses_mutator(
    codes: Dict[int, str] | None = None,
    per_method: Dict[str, Iterable[int]] | None = None,
):
    """
    Attach reusable responses by $ref if missing.
    per_method lets you restrict which statuses apply to which HTTP methods.
    """
    # defaults: broadly useful, but you can narrow with per_method
    codes = codes or {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        409: "Conflict",
        422: "ValidationError",
        429: "TooManyRequests",
        500: "ServerError",
    }
    per_method = per_method or {}

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, method, op in _iter_operations(schema):
            responses = op.setdefault("responses", {})
            method_allow = set(per_method.get(method.upper(), codes.keys()))
            for status, ref_name in codes.items():
                if status not in method_allow:
                    continue
                key = str(status)
                if key not in responses:
                    responses[key] = {"$ref": f"#/components/responses/{ref_name}"}
        return schema

    return m


# ------- pruning -------


def drop_unused_components_mutator(
    drop_responses: list[str] = None, drop_schemas: list[str] = None
):
    drop_responses = drop_responses or []
    drop_schemas = drop_schemas or []

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.get("components") or {}
        if drop_responses and "responses" in comps:
            for k in drop_responses:
                comps["responses"].pop(k, None)
        if drop_schemas and "schemas" in comps:
            for k in drop_schemas:
                comps["schemas"].pop(k, None)
        return schema

    return m
