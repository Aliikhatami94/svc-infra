from __future__ import annotations

import re
from typing import Dict, Iterable, Iterator, Tuple

from ..auth.security import auth_login_path
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


def pagination_components_mutator(
    *,
    default_limit: int = 50,
    max_limit: int = 200,
) -> callable:
    """
    Adds reusable pagination/filtering parameters & paginated envelope schemas.
    - Cursor: cursor/limit
    - Page: page/page_size
    - Common filters: q, sort, created_[after|before], updated_[after|before]
    - Envelope: PaginatedList<T>
    """

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {})
        params = comps.setdefault("parameters", {})
        schemas = comps.setdefault("schemas", {})

        # ---- Parameters (reusable) ----
        params.setdefault(
            "cursor",
            {
                "name": "cursor",
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": "Opaque cursor for forward pagination.",
            },
        )
        params.setdefault(
            "limit",
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": max_limit,
                    "default": default_limit,
                },
                "description": f"Max items to return (1..{max_limit}).",
            },
        )
        params.setdefault(
            "page",
            {
                "name": "page",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "minimum": 1, "default": 1},
                "description": "1-based page index (alternative to cursor).",
            },
        )
        params.setdefault(
            "page_size",
            {
                "name": "page_size",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": max_limit,
                    "default": default_limit,
                },
                "description": f"Number of items per page (1..{max_limit}).",
            },
        )
        params.setdefault(
            "q",
            {
                "name": "q",
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": "Free-text filter query.",
            },
        )
        params.setdefault(
            "sort",
            {
                "name": "sort",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "string",
                    "examples": ["created_at", "-created_at", "name", "-name"],
                },
                "description": "Sort field, prefix '-' for descending.",
            },
        )
        for fld in ("created", "updated"):
            params.setdefault(
                f"{fld}_after",
                {
                    "name": f"{fld}_after",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": f"Only items with {fld}_at strictly after this HTTP-date (RFC 9110).",
                },
            )
            params.setdefault(
                f"{fld}_before",
                {
                    "name": f"{fld}_before",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": f"Only items with {fld}_at strictly before this HTTP-date (RFC 9110).",
                },
            )

        # ---- Envelope schema (generic pattern) ----
        # This is a non-generic "template" envelope; concrete versions are produced per endpoint, if desired.
        schemas.setdefault(
            "PaginatedList",
            {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "object"}},
                    "next_cursor": {
                        "type": "string",
                        "nullable": True,
                        "description": "Opaque cursor for next page (null when no more).",
                    },
                    "total": {
                        "type": "integer",
                        "nullable": True,
                        "description": "Total items (may be null if not computed).",
                    },
                },
                "required": ["items"],
            },
        )

        return schema

    return m


def auto_attach_pagination_params_mutator(
    *,
    mode: str = "cursor_or_page",
    attach_filters: bool = True,
    apply_when: str = "array_200",
    flag_disable: str = "x_no_auto_pagination",
) -> callable:
    """
    Attaches reusable pagination/filter parameters to GET "listy" operations.

    - mode:
        "cursor_or_page" -> attach cursor+limit and page+page_size (clients use either)
        "cursor_only"    -> attach cursor+limit
        "page_only"      -> attach page+page_size
    - apply_when:
        "array_200" -> only when response 200 schema is an array
        "all_get"   -> for every GET op
    - Per-op opt-out: set operation's openapi_extra[flag_disable] = True
    """

    def _should_apply(op: dict) -> bool:
        if op.get(flag_disable) is True:
            return False
        if apply_when == "all_get":
            return True
        # array_200: inspect 200->application/json->schema
        resps = op.get("responses") or {}
        r200 = resps.get("200")
        if not isinstance(r200, dict):
            return False
        content = r200.get("content") or {}
        mt = content.get("application/json")
        if not isinstance(mt, dict):
            return False
        sch = mt.get("schema") or {}
        return isinstance(sch, dict) and sch.get("type") == "array"

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, method, op in _iter_ops(schema):
            if method != "get":
                continue
            if not _should_apply(op):
                continue

            params = op.setdefault("parameters", [])

            def _add_ref(name: str):
                params.append({"$ref": f"#/components/parameters/{name}"})

            if mode in ("cursor_only", "cursor_or_page"):
                _add_ref("cursor")
                _add_ref("limit")
            if mode in ("page_only", "cursor_or_page"):
                _add_ref("page")
                _add_ref("page_size")
            if attach_filters:
                _add_ref("q")
                _add_ref("sort")
                _add_ref("created_after")
                _add_ref("created_before")
                _add_ref("updated_after")
                _add_ref("updated_before")

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

        # Detect if any operation already references APIKeyHeader
        any_op_wants_api_key = False
        for _, _, op in _iter_ops(schema):
            for sec in op.get("security") or []:
                if isinstance(sec, dict) and "APIKeyHeader" in sec:
                    any_op_wants_api_key = True
                    break
            if any_op_wants_api_key:
                break

        # Add OAuth2 (always)
        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        comps.setdefault(
            "OAuth2PasswordBearer",
            {
                "type": "oauth2",
                "flows": {"password": {"tokenUrl": auth_login_path, "scopes": {}}},
            },
        )

        # Add API key scheme only if:
        #  - include_api_key flag is True (from spec/root), OR
        #  - at least one operation already references APIKeyHeader.
        if include_api_key or any_op_wants_api_key:
            comps.setdefault(
                "APIKeyHeader",
                {
                    "type": "apiKey",
                    "name": "X-API-Key",
                    "in": "header",
                },
            )

        # Normalize operation security (drop only 'SessionCookie')
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
    exclude_tags: set[str] | None = None,
    op_flag_disable: str = "x_disable_standard_responses",
):
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
    exclude_tags = exclude_tags or set()

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, method, op in _iter_ops(schema):
            if op.get(op_flag_disable) is True:
                continue
            if any(t in exclude_tags for t in (op.get("tags") or [])):
                continue

            allow = set(per_method.get(method.upper(), codes.keys()))
            responses = op.setdefault("responses", {})
            for status, ref_name in codes.items():
                if status not in allow:
                    continue
                k = str(status)
                if k not in responses:
                    responses[k] = {"$ref": f"#/components/responses/{ref_name}"}
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
    """Add missing descriptions; enforce required for path params; ensure schema exists.
    NOTE: Never touch $ref parameters here.
    """

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, _, op in _iter_ops(schema):
            params = op.get("parameters")
            if not isinstance(params, list):
                continue
            for p in params:
                if not isinstance(p, dict):
                    continue
                if "$ref" in p:
                    # leave component parameters untouched
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


def strip_ref_siblings_in_parameters_mutator():
    """Normalize parameters: if an item has $ref, remove all other keys."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            params = op.get("parameters")
            if not isinstance(params, list):
                continue
            for p in params:
                if isinstance(p, dict) and "$ref" in p and len(p) > 1:
                    ref = p["$ref"]
                    p.clear()
                    p["$ref"] = ref
        return schema

    return m


def dedupe_parameters_mutator():
    """
    Deduplicate operation.parameters by actual (name, in):
      - Prefer **inline** params over $ref so per-op 'required: true' (e.g., Idempotency-Key) wins.
      - Collapse duplicate $refs.
      - If a $ref and an inline share the same (name, in), keep the inline and drop the $ref.
    """

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.get("components") or {}
        comp_params = (comps.get("parameters") or {}).copy()

        def _resolve_ref(ref: str) -> tuple[str, str] | None:
            # '#/components/parameters/<Key>' -> ('Idempotency-Key','header'), etc.
            try:
                key = ref.rsplit("/", 1)[-1]
                p = comp_params.get(key) or {}
                name = p.get("name")
                where = p.get("in")
                if isinstance(name, str) and isinstance(where, str):
                    return (name, where)
            except Exception:
                pass
            return None

        for _, _, op in _iter_ops(schema):
            params = op.get("parameters")
            if not isinstance(params, list) or not params:
                continue

            # First pass: collect inline params by (name, in)
            inline_by_key: dict[tuple[str, str], dict] = {}
            for p in params:
                if isinstance(p, dict) and "$ref" not in p:
                    name = p.get("name")
                    where = p.get("in")
                    if isinstance(name, str) and isinstance(where, str):
                        # Prefer the first inline; later duplicates ignored
                        inline_by_key.setdefault((name, where), p)

            seen_ref_targets: set[str] = set()
            seen_keys: set[tuple[str, str]] = set()
            result: list[dict] = []

            for p in params:
                if not isinstance(p, dict):
                    continue

                if "$ref" in p:
                    ref = p.get("$ref")
                    if not isinstance(ref, str):
                        continue
                    # de-dup exact same $ref
                    if ref in seen_ref_targets:
                        continue
                    seen_ref_targets.add(ref)

                    tup = _resolve_ref(ref)
                    if tup is None:
                        # keep unresolved ref (unlikely)
                        result.append({"$ref": ref})
                        continue

                    # If an inline with same (name, in) exists, prefer inline, skip this $ref
                    if tup in inline_by_key:
                        continue

                    # Else, keep this $ref if we didn't already keep a param for that key
                    if tup in seen_keys:
                        continue
                    seen_keys.add(tup)
                    # Ensure no siblings remain
                    result.append({"$ref": ref})
                    continue

                # inline param
                name = p.get("name")
                where = p.get("in")
                if not (isinstance(name, str) and isinstance(where, str)):
                    result.append(p)
                    continue
                key = (name, where)
                if key in seen_keys:
                    # already kept an inline with same (name, in)
                    continue
                seen_keys.add(key)
                result.append(p)

            op["parameters"] = result

        return schema

    return m


def normalize_no_content_204_mutator():
    """Ensure 204 responses have 'No Content' description and no content."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if not isinstance(resps, dict):
                continue
            r204 = resps.get("204")
            if isinstance(r204, dict):
                # Always normalize text to the conventional phrasing
                r204["description"] = "No Content"
                # Many validators prefer no 'content' for 204
                if "content" in r204:
                    r204.pop("content", None)
        return schema

    return m


def inject_safe_examples_mutator():
    """
    Inject a couple of specific, schema-safe examples:
      - If a 2xx application/json response uses #/components/schemas/SendEmailCodeOut
        and has no example(s), set {"sent": true, "cooldown_seconds": 60}.
      - For GET/any 2xx on /ping, add {"status": "ok"} if example(s) are missing.
    Never overwrites existing example/examples.
    """

    def _has_examples(mt_obj: dict) -> bool:
        return isinstance(mt_obj, dict) and ("example" in mt_obj or "examples" in mt_obj)

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, method, op in _iter_ops(schema):
            resps = op.get("responses") or {}
            for code, resp in resps.items():
                if not isinstance(resp, dict):
                    continue
                try:
                    ic = int(code)
                except Exception:
                    continue
                if not (200 <= ic < 300):
                    continue

                content = resp.get("content") or {}
                mt_obj = content.get("application/json")
                if not isinstance(mt_obj, dict) or _has_examples(mt_obj):
                    continue

                # Special-case: SendEmailCodeOut by $ref
                sch = mt_obj.get("schema") or {}
                ref = sch.get("$ref") if isinstance(sch, dict) else None
                if isinstance(ref, str) and ref.endswith("/SendEmailCodeOut"):
                    mt_obj["example"] = {"sent": True, "cooldown_seconds": 60}
                    continue

                # Special-case: /ping success body
                if path == "/ping":
                    mt_obj["example"] = {"status": "ok"}

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
        "string": "string",
        "integer": 0,
        "number": 0,
        "boolean": True,
    }

    def _infer_example(sch: dict):
        if not isinstance(sch, dict):
            return None
        t = sch.get("type")
        if t in example_by_type:
            return example_by_type[t]
        if t == "array":
            item = sch.get("items") or {}
            ex = _infer_example(item)
            return [] if ex is None else [ex]
        # for object/$ref/unknown → don’t auto-example
        return None

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses") or {}
            for code, resp in resps.items():
                if not isinstance(resp, dict):
                    continue
                try:
                    ic = int(code)
                except Exception:
                    continue
                # Only touch 2xx, not 204, and only application/json
                if not (200 <= ic < 300) or ic == 204:
                    continue
                content = resp.get("content") or {}
                mt_obj = content.get("application/json")
                if not isinstance(mt_obj, dict):
                    continue
                if "example" in mt_obj or "examples" in mt_obj:
                    continue
                sch = mt_obj.get("schema") or {}
                ex = _infer_example(sch)
                if ex is not None:
                    mt_obj["example"] = ex
        return schema

    return m


def ensure_media_examples_mutator():
    """
    Add minimal examples only when they are guaranteed valid:
    - primitives: string/integer/number/boolean
    - arrays: []
    Never add examples for object/$ref schemas (they usually have required fields).
    Skip application/problem+json entirely.
    """

    PRIMITIVE_EX = {"string": "", "integer": 0, "number": 0, "boolean": False}

    def _should_skip_media_type(mt: str) -> bool:
        # don't touch problem+json (examples live in components.responses)
        return mt == "application/problem+json"

    def _minimal_example(sch: dict):
        if not isinstance(sch, dict):
            return None
        if "$ref" in sch:
            return None
        t = sch.get("type")
        # object-ish → skip (likely has required/properties)
        if t == "object" or "properties" in sch or "required" in sch:
            return None
        if t == "array":
            # [] is always schema-valid regardless of items' required
            return []
        if t in PRIMITIVE_EX:
            return PRIMITIVE_EX[t]
        return None

    def patch_content(node: dict):
        content = node.get("content")
        if not isinstance(content, dict):
            return
        for mt, mt_obj in content.items():
            if not isinstance(mt_obj, dict) or _should_skip_media_type(mt):
                continue
            if "example" in mt_obj or "examples" in mt_obj:
                continue
            sch = mt_obj.get("schema")
            ex = _minimal_example(sch if isinstance(sch, dict) else {})
            if ex is not None:
                mt_obj["example"] = ex

    def m(schema: dict) -> dict:
        schema = dict(schema)

        # responses
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if isinstance(resps, dict):
                for resp in resps.values():
                    if isinstance(resp, dict):
                        patch_content(resp)

            # request bodies
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


def ensure_success_examples_mutator():
    """Ensure 2xx application/json responses have an example (but only when safe)."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses") or {}
            for code, resp in resps.items():
                if not isinstance(resp, dict):
                    continue
                try:
                    ic = int(code)
                except Exception:
                    continue
                if not (200 <= ic < 300) or ic == 204:
                    continue
                mt_obj = (resp.get("content") or {}).get("application/json")
                if not isinstance(mt_obj, dict) or "example" in mt_obj or "examples" in mt_obj:
                    continue
                sch = mt_obj.get("schema") or {}

                # Only set examples for primitives/arrays. Never for object/$ref.
                t = sch.get("type")
                if t == "string":
                    mt_obj["example"] = "example"
                elif t == "boolean":
                    mt_obj["example"] = True
                elif t == "integer":
                    mt_obj["example"] = 0
                elif t == "array":
                    mt_obj["example"] = []
                # NOTE: no else/fallback for object/$ref
        return schema

    return m


# --- NEW: attach minimal x-codeSamples for common operations ---
def attach_code_samples_mutator():
    """Attach minimal curl/httpie x-codeSamples for each operation if missing.

    We avoid templating parameters; samples illustrate method and path only.
    """

    def m(schema: dict) -> dict:
        schema = dict(schema)
        servers = schema.get("servers") or [{"url": ""}]
        base = servers[0].get("url") or ""

        for path, method, op in _iter_ops(schema):
            # Don't override existing samples
            if isinstance(op.get("x-codeSamples"), list) and op["x-codeSamples"]:
                continue
            url = f"{base}{path}"
            method_up = method.upper()
            samples = [
                {
                    "lang": "bash",
                    "label": "curl",
                    "source": f"curl -X {method_up} '{url}'",
                },
                {
                    "lang": "bash",
                    "label": "httpie",
                    "source": f"http {method_up} '{url}'",
                },
            ]
            op["x-codeSamples"] = samples
        return schema

    return m


# --- NEW: ensure Problem+JSON examples exist for standard error responses ---
def ensure_problem_examples_mutator():
    """Add example objects for 4xx/5xx responses using Problem schema if absent."""

    try:
        # Internal helper with sensible defaults
        from .conventions import _problem_example  # type: ignore
    except Exception:  # pragma: no cover - fallback

        def _problem_example(**kw):  # type: ignore
            base = {
                "type": "about:blank",
                "title": "Error",
                "status": 500,
                "detail": "An error occurred.",
                "instance": "/request/trace",
                "code": "INTERNAL_ERROR",
            }
            base.update(kw)
            return base

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses") or {}
            for code, resp in resps.items():
                if not isinstance(resp, dict):
                    continue
                try:
                    ic = int(code)
                except Exception:
                    continue
                if ic < 400:
                    continue
                # Do not add content if response is a $ref; avoid creating siblings
                if "$ref" in resp:
                    continue
                content = resp.setdefault("content", {})
                # prefer problem+json but also set application/json if present
                for mt in ("application/problem+json", "application/json"):
                    mt_obj = content.get(mt)
                    if mt_obj is None:
                        # Create a basic media type referencing Problem schema when appropriate
                        if mt == "application/problem+json":
                            mt_obj = {"schema": {"$ref": "#/components/schemas/Problem"}}
                            content[mt] = mt_obj
                        else:
                            continue
                    if not isinstance(mt_obj, dict):
                        continue
                    if "example" in mt_obj or "examples" in mt_obj:
                        continue
                    mt_obj["example"] = _problem_example(status=ic)
        return schema

    return m


# --- NEW: attach default tags from first path segment when missing ---
def attach_default_tags_mutator():
    """If an operation has no tags, tag it by its first path segment."""

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for path, _method, op in _iter_ops(schema):
            tags = op.get("tags")
            if tags:
                continue
            seg = path.strip("/").split("/", 1)[0] or "root"
            op["tags"] = [seg]
        return schema

    return m


def dedupe_tags_mutator():
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            tags = op.get("tags")
            if isinstance(tags, list):
                op["tags"] = list(dict.fromkeys(tags))  # preserve order, drop dups
        return schema

    return m


def scrub_invalid_object_examples_mutator():
    """
    Remove media examples that are objects but don't satisfy required keys
    (or when schema is a $ref/object). Keeps primitives/arrays.
    """

    def _invalid_object_example(sch: dict, ex: dict) -> bool:
        if not isinstance(sch, dict) or not isinstance(ex, dict):
            return False
        if "$ref" in sch:
            return True  # can't validate here → drop
        if sch.get("type") == "object" or "properties" in sch or "required" in sch:
            req = set(sch.get("required") or [])
            return bool(req) and not req.issubset(ex.keys())
        return False

    def _patch(node: dict):
        content = node.get("content")
        if not isinstance(content, dict):
            return
        for mt_obj in content.values():
            if not isinstance(mt_obj, dict):
                continue
            sch = mt_obj.get("schema")
            ex = mt_obj.get("example")
            if "example" in mt_obj and _invalid_object_example(
                sch if isinstance(sch, dict) else {}, ex
            ):
                mt_obj.pop("example", None)

    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, _, op in _iter_ops(schema):
            resps = op.get("responses")
            if isinstance(resps, dict):
                for resp in resps.values():
                    if isinstance(resp, dict):
                        _patch(resp)
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                _patch(rb)
        return schema

    return m


def drop_unused_components_mutator_auto(keep_schemas: set[str] | None = None):
    keep_schemas = set(keep_schemas or {"Problem"})
    REF_RE = re.compile(
        r"#/components/(?P<section>schemas|responses|parameters|headers|requestBodies|securitySchemes|links|callbacks)/(?P<name>[^/\s]+)"
    )

    def collect_refs(node, out: dict[str, set[str]]):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    m = REF_RE.match(v)
                    if m:
                        out.setdefault(m.group("section"), set()).add(m.group("name"))
                else:
                    collect_refs(v, out)
        elif isinstance(node, list):
            for v in node:
                collect_refs(v, out)

    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.get("components") or {}
        used: dict[str, set[str]] = {}
        collect_refs(schema, used)

        # schemas
        sch = comps.get("schemas") or {}
        for name in list(sch.keys()):
            if name not in keep_schemas and name not in (used.get("schemas") or set()):
                sch.pop(name, None)

        # responses
        resps = comps.get("responses") or {}
        for name in list(resps.keys()):
            if name not in (used.get("responses") or set()):
                resps.pop(name, None)

        # NEW: headers
        hdrs = comps.get("headers") or {}
        for name in list(hdrs.keys()):
            if name not in (used.get("headers") or set()):
                hdrs.pop(name, None)

        # (Optional: parameters/requestBodies/etc. same pattern)

        return schema

    return m


def hardening_components_mutator():
    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {})
        params = comps.setdefault("parameters", {})
        headers = comps.setdefault("headers", {})

        params.setdefault(
            "IdempotencyKey",
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Provide to make the request idempotent for 24h.",
            },
        )
        params.setdefault(
            "IfNoneMatch",
            {
                "name": "If-None-Match",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Conditional GET (ETag).",
            },
        )
        params.setdefault(
            "IfModifiedSince",
            {
                "name": "If-Modified-Since",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Conditional GET. HTTP-date per RFC 9110 (e.g. 'Wed, 01 Jan 2025 00:00:00 GMT').",
            },
        )
        params.setdefault(
            "IfMatch",
            {
                "name": "If-Match",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Optimistic concurrency for updates.",
            },
        )

        headers.setdefault(
            "ETag", {"schema": {"type": "string"}, "description": "Opaque entity tag."}
        )
        headers.setdefault(
            "LastModified",
            {
                "schema": {"type": "string"},  # HTTP-date string
                "description": "Last modification time, HTTP-date per RFC 9110.",
            },
        )
        headers.setdefault(
            "XRateLimitLimit", {"schema": {"type": "integer"}, "description": "Tokens in window."}
        )
        headers.setdefault(
            "XRateLimitRemaining",
            {"schema": {"type": "integer"}, "description": "Remaining tokens."},
        )
        headers.setdefault(
            "XRateLimitReset", {"schema": {"type": "integer"}, "description": "Unix reset time."}
        )
        headers.setdefault(
            "XRequestId", {"schema": {"type": "string"}, "description": "Correlation id."}
        )
        headers.setdefault(
            "Deprecation",
            {
                "schema": {"type": "string"},
                "description": "Set to 'true' for deprecated endpoints.",
            },
        )
        headers.setdefault(
            "Sunset",
            {"schema": {"type": "string"}, "description": "HTTP-date for deprecation sunset."},
        )
        return schema

    return m


def attach_header_params_mutator():
    def m(schema: dict) -> dict:
        schema = dict(schema)
        comps = schema.setdefault("components", {})
        comp_params = comps.setdefault("parameters", {})

        def _component_param_name(ref: str) -> tuple[str, str] | None:
            try:
                key = ref.rsplit("/", 1)[-1]
                p = comp_params.get(key) or {}
                name = p.get("name")
                where = p.get("in")
                if isinstance(name, str) and isinstance(where, str):
                    return (name, where)
            except Exception:
                pass
            return None

        for _, method, op in _iter_ops(schema):
            params = op.setdefault("parameters", [])

            # What inline params (non-$ref) are already present?
            inline_names = {
                (p.get("name"), p.get("in"))
                for p in params
                if isinstance(p, dict) and "$ref" not in p and "name" in p and "in" in p
            }

            def add_ref_if_absent(name: str):
                ref = {"$ref": f"#/components/parameters/{name}"}
                tup = _component_param_name(ref["$ref"])
                # If an inline with the same (name, in) exists (e.g., from a dependency),
                # don't add the ref at all.
                if tup and tup in inline_names:
                    return
                params.append(ref)

            # ---- Write methods: Idempotency-Key fallback (optional via $ref) ----
            # If the dependency added an inline required param, nothing to do;
            # otherwise, add the optional component ref so callers can still send it.
            if method in ("post", "patch", "delete"):
                if ("Idempotency-Key", "header") not in inline_names:
                    add_ref_if_absent("IdempotencyKey")
                # Optional optimistic concurrency for updates
                if method in ("patch", "put"):
                    add_ref_if_absent("IfMatch")

            # ---- Conditional GET headers (optional via $ref) ----
            if method == "get":
                add_ref_if_absent("IfNoneMatch")
                add_ref_if_absent("IfModifiedSince")

            # ---- Standard success/429 headers (unchanged) ----
            resps = op.get("responses") or {}
            for code, resp in resps.items():
                try:
                    ic = int(code)
                except Exception:
                    continue
                if 200 <= ic < 300:
                    hdrs = resp.setdefault("headers", {})
                    hdrs.setdefault("ETag", {"$ref": "#/components/headers/ETag"})
                    hdrs.setdefault("Last-Modified", {"$ref": "#/components/headers/LastModified"})
                    hdrs.setdefault("X-Request-Id", {"$ref": "#/components/headers/XRequestId"})
                    hdrs.setdefault(
                        "X-RateLimit-Limit", {"$ref": "#/components/headers/XRateLimitLimit"}
                    )
                    hdrs.setdefault(
                        "X-RateLimit-Remaining",
                        {"$ref": "#/components/headers/XRateLimitRemaining"},
                    )
                    hdrs.setdefault(
                        "X-RateLimit-Reset", {"$ref": "#/components/headers/XRateLimitReset"}
                    )
                if code == "429":
                    resp.setdefault("headers", {})["Retry-After"] = {
                        "schema": {"type": "integer"},
                        "description": "Seconds until next allowed request.",
                    }

        return schema

    return m


def attach_conditional_get_304_mutator():
    def m(schema: dict) -> dict:
        schema = dict(schema)
        for _, method, op in _iter_ops(schema):
            if method != "get":
                continue
            resps = op.setdefault("responses", {})
            resps.setdefault(
                "304",
                {
                    "description": "Not Modified",
                    "headers": {
                        "ETag": {"$ref": "#/components/headers/ETag"},
                        "Last-Modified": {"$ref": "#/components/headers/LastModified"},
                        "X-Request-Id": {"$ref": "#/components/headers/XRequestId"},
                    },
                },
            )
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
        hardening_components_mutator(),
        attach_header_params_mutator(),
        normalize_problem_and_examples_mutator(),
        attach_standard_responses_mutator(),
        attach_conditional_get_304_mutator(),
        auth_mutator(include_api_key),
        strip_ref_siblings_in_responses_mutator(),
        prune_invalid_responses_keys_mutator(),
        strip_ref_siblings_in_parameters_mutator(),
        dedupe_parameters_mutator(),
        ensure_operation_descriptions_mutator(),
        ensure_request_body_descriptions_mutator(),
        ensure_parameter_metadata_mutator(),
        ensure_media_type_schemas_mutator(),
        ensure_examples_for_json_mutator(),
        ensure_success_examples_mutator(),
        attach_default_tags_mutator(),
        attach_code_samples_mutator(),
        ensure_problem_examples_mutator(),
        ensure_media_examples_mutator(),
        scrub_invalid_object_examples_mutator(),
        normalize_no_content_204_mutator(),
        ensure_response_descriptions_mutator(),
        improve_success_response_descriptions_mutator(),
        inject_safe_examples_mutator(),
        dedupe_tags_mutator(),
        ensure_global_tags_mutator(),
        drop_unused_components_mutator_auto(),
        info_mutator(service, spec),
    ]
    if server_url:
        mutators.append(servers_mutator(server_url))
    return mutators
