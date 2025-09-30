from __future__ import annotations

from typing import Dict, Iterable, Iterator, Tuple

from .models import APIVersionSpec, ServiceInfo, VersionInfo

_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _iter_ops(schema: dict) -> Iterator[Tuple[str, str, dict]]:
    """Yield (path, method, op) for each operation object."""
    paths = schema.get("paths") or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() in _HTTP_METHODS and isinstance(op, dict):
                yield path, method.lower(), op


def _ensure_schema(node: dict, default: dict | None = None):
    default = default or {"type": "object", "additionalProperties": True}
    sch = node.get("schema")
    if not isinstance(sch, dict) or not sch:
        node["schema"] = dict(default)


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
        for _, _, op in _iter_ops(schema):
            op["security"] = _normalize_security_list(op.get("security"), drop)

        return schema

    return _m


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


def servers_mutator(url: str):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        schema["servers"] = [{"url": url}]
        return schema

    return m


def ensure_operation_descriptions_mutator(template: str = "{method} {path}."):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, method, op in _iter_ops(schema):
            desc = op.get("description")
            if not isinstance(desc, str) or not desc.strip():
                op["description"] = template.format(method=method.upper(), path=path)
        return schema

    return m


def ensure_global_tags_mutator(default_desc: str = "Operations related to {tag}."):
    def m(schema: dict) -> dict:
        schema = dict(schema)

        # collect all tags used by operations
        used: set[str] = set()
        for _, _, op in _iter_ops(schema):
            for t in op.get("tags") or []:
                if isinstance(t, str):
                    used.add(t)

        # map existing tags by name and preserve their fields
        existing_list = schema.get("tags") or []
        existing_map: Dict[str, dict] = {}
        for item in existing_list:
            if isinstance(item, dict) and "name" in item:
                existing_map[item["name"]] = dict(item)

        # add missing tags; do NOT override existing descriptions
        for name in sorted(used):
            if name not in existing_map:
                existing_map[name] = {"name": name, "description": default_desc.format(tag=name)}
            else:
                if not existing_map[name].get("description"):
                    existing_map[name]["description"] = default_desc.format(tag=name)

        if existing_map:
            schema["tags"] = sorted(existing_map.values(), key=lambda x: x.get("name", ""))

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
        for _, method, op in _iter_ops(schema):
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


def ensure_response_descriptions_mutator():
    """Ensure every response has a non-empty description."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            for code, resp in list(resps.items()):
                if not isinstance(resp, dict):
                    continue
                if "$ref" in resp:
                    continue
                desc = resp.get("description")
                if not isinstance(desc, str) or not desc.strip():
                    # sensible defaults by class
                    try:
                        ic = int(code) if code != "default" else 200
                    except Exception:
                        ic = 200
                    if 200 <= ic < 300:
                        resp["description"] = "Successful response"
                    elif ic == 204:
                        resp["description"] = "No Content"
                    elif ic == 400:
                        resp["description"] = "Bad Request"
                    elif ic == 401:
                        resp["description"] = "Unauthorized"
                    elif ic == 403:
                        resp["description"] = "Forbidden"
                    elif ic == 404:
                        resp["description"] = "Not Found"
                    elif ic == 409:
                        resp["description"] = "Conflict"
                    elif ic == 422:
                        resp["description"] = "Unprocessable Entity"
                    elif ic == 429:
                        resp["description"] = "Too Many Requests"
                    elif 500 <= ic < 600:
                        resp["description"] = "Internal Server Error"
                    else:
                        resp["description"] = f"HTTP {code}"
        return schema

    return m


def ensure_media_type_schemas_mutator():
    """Make sure every content media type has a non-empty schema."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            # responses
            resps = op.get("responses")
            if isinstance(resps, dict):
                for resp in resps.values():
                    if not isinstance(resp, dict):
                        continue
                    content = resp.get("content")
                    if isinstance(content, dict):
                        for mt, mt_obj in content.items():
                            if isinstance(mt_obj, dict):
                                _ensure_schema(mt_obj)
            # requestBody
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                content = rb.get("content")
                if isinstance(content, dict):
                    for mt, mt_obj in content.items():
                        if isinstance(mt_obj, dict):
                            _ensure_schema(mt_obj)
            # no special casing of text/plain etc.; adjust if needed
        return schema

    return m


# ---------- 3) Request body descriptions ----------
def ensure_request_body_descriptions_mutator(default_template="Request body for {method} {path}."):
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, method, op in _iter_ops(schema):
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                desc = rb.get("description")
                if not isinstance(desc, str) or not desc.strip():
                    rb["description"] = default_template.format(method=method.upper(), path=path)
        return schema

    return m


def ensure_parameter_metadata_mutator(param_desc_template="{name} parameter."):
    """Add missing descriptions; enforce required for path params; ensure schema exists."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, _, op in _iter_ops(schema):
            params = op.get("parameters")
            if not isinstance(params, list):
                continue
            for p in params:
                if not isinstance(p, dict):
                    continue
                name = p.get("name", "")
                where = p.get("in", "")
                # description
                desc = p.get("description")
                if not isinstance(desc, str) or not desc.strip():
                    p["description"] = param_desc_template.format(name=name)
                # required for path params
                if where == "path":
                    p["required"] = True
                # ensure schema
                sch = p.get("schema")
                if not isinstance(sch, dict) or not sch.get("type"):
                    p["schema"] = sch if isinstance(sch, dict) else {}
                    p["schema"].setdefault("type", "string")
        return schema

    return m


def normalize_no_content_204_mutator():
    """Ensure 204 responses have description and no content."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            r204 = resps.get("204")
            if isinstance(r204, dict):
                r204.setdefault("description", "No Content")
                # many validators prefer no 'content' for 204
                if "content" in r204:
                    r204.pop("content", None)
        return schema

    return m


def prune_invalid_responses_keys_mutator():
    """In an operation's responses object, only status codes or 'default' are allowed."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            for k in list(resps.keys()):
                if k == "default":
                    continue
                if k.isdigit() and 100 <= int(k) <= 599:
                    continue
                # stray keys like 'description' under responses -> drop
                resps.pop(k, None)
        return schema

    return m


def strip_ref_siblings_in_responses_mutator():
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            for code, resp in list(resps.items()):
                if isinstance(resp, dict) and "$ref" in resp and len(resp) > 1:
                    ref = resp["$ref"]
                    resp.clear()
                    resp["$ref"] = ref
        return schema

    return m


def ensure_examples_for_json_mutator(example_by_type=None):
    example_by_type = example_by_type or {
        "object": {},
        "array": [],
        "string": "string",
        "integer": 0,
        "number": 0,
        "boolean": True,
    }

    def _infer_example(schema: dict):
        if not isinstance(schema, dict):
            return {}
        t = schema.get("type")
        if t in example_by_type:
            return example_by_type[t]
        if "$ref" in schema or "properties" in schema or "additionalProperties" in schema:
            return {}
        return {}

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            # responses
            resps = op.get("responses") or {}
            for resp in resps.values():
                if not isinstance(resp, dict):
                    continue
                content = resp.get("content") or {}
                for mt, mt_obj in content.items():
                    if not isinstance(mt_obj, dict) or not mt.startswith("application/"):
                        continue
                    if "example" in mt_obj or "examples" in mt_obj:
                        continue
                    sch = mt_obj.get("schema") or {}
                    ex = _infer_example(sch)
                    if ex != {}:
                        mt_obj["example"] = ex
            # request bodies
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                content = rb.get("content") or {}
                for mt, mt_obj in content.items():
                    if not isinstance(mt_obj, dict) or not mt.startswith("application/"):
                        continue
                    if "example" in mt_obj or "examples" in mt_obj:
                        continue
                    sch = mt_obj.get("schema") or {}
                    ex = _infer_example(sch)
                    if ex != {}:
                        mt_obj["example"] = ex
        return schema

    return m


def ensure_media_examples_mutator():
    """
    If a media-type object has a schema but neither 'example' nor 'examples',
    attach a minimal 'example' derived from the schema shape.
    """

    def _minimal_example(sch: dict) -> object:
        if not isinstance(sch, dict):
            return {}
        t = sch.get("type")
        if t == "array":
            return []
        if t == "string":
            return ""
        if t == "integer":
            return 0
        if t == "number":
            return 0
        if t == "boolean":
            return False
        # If it's an object or $ref or unknown -> {}
        return {}

    def m(schema: dict) -> dict:
        schema = dict(schema)

        def patch_content(node: dict):
            content = node.get("content")
            if not isinstance(content, dict):
                return
            for mt, mt_obj in content.items():
                if not isinstance(mt_obj, dict):
                    continue
                if "example" in mt_obj or "examples" in mt_obj:
                    continue
                sch = mt_obj.get("schema")
                if isinstance(sch, dict):
                    mt_obj["example"] = _minimal_example(sch)

        # responses
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if isinstance(resps, dict):
                for resp in resps.values():
                    if isinstance(resp, dict):
                        patch_content(resp)

            # request bodies (some “API doctors” also check these)
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                patch_content(rb)

        return schema

    return m


def improve_success_response_descriptions_mutator():
    """
    If a 2xx response description is the generic 'Successful Response' or empty,
    replace with a more specific, deterministic description based on summary/method/path.
    Never touch non-2xx or custom texts.
    """

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, method, op in _iter_ops(schema):
            summary = (op.get("summary") or "").strip()
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            for code, resp in resps.items():
                if not isinstance(resp, dict) or "$ref" in resp:
                    continue
                if code == "default":
                    continue
                try:
                    ic = int(code)
                except Exception:
                    continue
                if ic == 204:
                    # will be handled by your 204 mutator; do nothing here
                    continue
                if 200 <= ic < 300:
                    desc = (resp.get("description") or "").strip()
                    if not desc or desc.lower() == "successful response":
                        if summary:
                            resp["description"] = f"{summary} success"
                        else:
                            resp["description"] = f"{method.upper()} {path} success"
        return schema

    return m


def setup_mutators(
    service: ServiceInfo,
    spec: APIVersionSpec | None,
    include_api_key: bool = False,
    server_url: str | None = None,
) -> list:
    mutators = [
        conventions_mutator(),
        normalize_problem_and_examples_mutator(),
        attach_standard_responses_mutator(),
        auth_mutator(include_api_key),
        strip_ref_siblings_in_responses_mutator(),
        prune_invalid_responses_keys_mutator(),
        ensure_operation_descriptions_mutator(),
        ensure_request_body_descriptions_mutator(),
        ensure_parameter_metadata_mutator(),
        ensure_media_type_schemas_mutator(),
        ensure_examples_for_json_mutator(),
        normalize_no_content_204_mutator(),
        ensure_response_descriptions_mutator(),
        improve_success_response_descriptions_mutator(),
        ensure_global_tags_mutator(),
        drop_unused_components_mutator(),
        info_mutator(service, spec),
        ensure_media_examples_mutator(),
    ]
    if server_url:
        mutators.append(servers_mutator(server_url))

    return mutators
