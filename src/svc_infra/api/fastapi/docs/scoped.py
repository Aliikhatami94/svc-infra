from __future__ import annotations

import copy
from typing import Dict, Iterable, List, Optional, Set, Tuple

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

# (prefix, swagger_path, redoc_path, openapi_path, title)
DOC_SCOPES: List[Tuple[str, str, str, str, str]] = []

_HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}

# ---------------------- path & ref helpers ----------------------


def _path_included(
    path: str,
    include_prefixes: Optional[Iterable[str]] = None,
    exclude_prefixes: Optional[Iterable[str]] = None,
) -> bool:
    def _match(pfx: str) -> bool:
        pfx = pfx.rstrip("/") or "/"
        return path == pfx or path.startswith(pfx + "/")

    if include_prefixes:
        if not any(_match(p) for p in include_prefixes):
            return False
    if exclude_prefixes:
        if any(_match(p) for p in exclude_prefixes):
            return False
    return True


def _collect_refs(obj, refset: Set[Tuple[str, str]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/components/"):
                parts = v.split("/")
                if len(parts) >= 4:
                    refset.add((parts[2], parts[3]))
            else:
                _collect_refs(v, refset)
    elif isinstance(obj, list):
        for it in obj:
            _collect_refs(it, refset)


def _close_over_component_refs(
    full_components: Dict, initial: Set[Tuple[str, str]]
) -> Set[Tuple[str, str]]:
    to_visit = list(initial)
    seen = set(initial)
    while to_visit:
        section, name = to_visit.pop()
        section_map = (full_components or {}).get(section) or {}
        comp = section_map.get(name)
        if not isinstance(comp, dict):
            continue
        nested: Set[Tuple[str, str]] = set()
        _collect_refs(comp, nested)
        for ref in nested:
            if ref not in seen:
                seen.add(ref)
                to_visit.append(ref)
    return seen


def _prune_to_paths(
    full_schema: Dict, keep_paths: Dict[str, dict], title_suffix: Optional[str]
) -> Dict:
    schema = copy.deepcopy(full_schema)
    schema["paths"] = keep_paths

    used_tags: Set[str] = set()
    direct_refs: Set[Tuple[str, str]] = set()
    used_security_schemes: Set[str] = set()

    for path_item in keep_paths.values():
        for method, op in path_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            for t in op.get("tags", []) or []:
                used_tags.add(t)
            _collect_refs(op, direct_refs)
            for sec in op.get("security", []) or []:
                for scheme_name in sec.keys():
                    used_security_schemes.add(scheme_name)

    comps = schema.get("components") or {}
    all_refs = _close_over_component_refs(comps, direct_refs)

    pruned_components: Dict[str, Dict] = {}
    if isinstance(comps, dict):
        for section, items in comps.items():
            keep_names = {name for (sec, name) in all_refs if sec == section}
            if section == "securitySchemes":
                keep_names |= used_security_schemes
            if not keep_names:
                continue
            section_map = items or {}
            pruned = {name: section_map[name] for name in keep_names if name in section_map}
            if pruned:
                pruned_components[section] = pruned
    schema["components"] = pruned_components if pruned_components else {}

    if "tags" in schema and isinstance(schema["tags"], list):
        schema["tags"] = [
            t for t in schema["tags"] if isinstance(t, dict) and t.get("name") in used_tags
        ]

    info = dict(schema.get("info") or {})
    if title_suffix:
        base_title = info.get("title") or "API"
        info["title"] = f"{base_title} • {title_suffix}"
    schema["info"] = info
    return schema


def _build_filtered_schema(
    full_schema: Dict,
    *,
    include_prefixes: Optional[List[str]] = None,
    exclude_prefixes: Optional[List[str]] = None,
    title_suffix: Optional[str] = None,
) -> Dict:
    paths = full_schema.get("paths", {}) or {}
    keep_paths = {
        p: v for p, v in paths.items() if _path_included(p, include_prefixes, exclude_prefixes)
    }
    return _prune_to_paths(full_schema, keep_paths, title_suffix)


# ---------------------- root filtering core ----------------------


def _ensure_original_openapi_saved(app: FastAPI) -> None:
    # Keep a pointer to the unfiltered function exactly once
    if not hasattr(app.state, "_scoped_original_openapi"):
        app.state._scoped_original_openapi = app.openapi  # type: ignore[attr-defined]


def _get_full_schema_from_original(app: FastAPI) -> Dict:
    # Always read from the original (unfiltered) OpenAPI source
    _ensure_original_openapi_saved(app)
    return copy.deepcopy(app.state._scoped_original_openapi())  # type: ignore[attr-defined]


def _install_root_filter(app: FastAPI, exclude_prefixes: List[str]) -> None:
    _ensure_original_openapi_saved(app)
    app.state._scoped_root_exclusions = sorted(set(exclude_prefixes))  # type: ignore[attr-defined]

    def root_filtered_openapi():
        full_schema = _get_full_schema_from_original(app)
        return _build_filtered_schema(
            full_schema,
            exclude_prefixes=app.state._scoped_root_exclusions,  # type: ignore[attr-defined]
            title_suffix=None,
        )

    app.openapi = root_filtered_openapi  # swap only the root presenter


def _current_registered_scopes() -> List[str]:
    return [scope for (scope, *_rest) in DOC_SCOPES]


def _ensure_root_excludes_registered_scopes(app: FastAPI) -> None:
    scopes = _current_registered_scopes()
    if scopes:
        _install_root_filter(app, scopes)


# ---------------------- public API ----------------------


def add_prefixed_docs(
    app: FastAPI, *, prefix: str, title: str, auto_exclude_from_root: bool = True
) -> None:
    """
    Expose filtered OpenAPI + Swagger/ReDoc for only the routes under `prefix`.
    - OpenAPI:  {prefix}/openapi.json
    - Swagger:  {prefix}/docs
    - ReDoc:    {prefix}/redoc
    Also (by default) registers the scope so the ROOT spec auto-excludes it.
    """
    scope = prefix.rstrip("/") or "/"
    openapi_path = f"{scope}/openapi.json"
    swagger_path = f"{scope}/docs"
    redoc_path = f"{scope}/redoc"

    # ensure we can always read the full schema regardless of later root filtering
    _ensure_original_openapi_saved(app)

    # Per-scope cache (optional)
    _scope_cache: Dict | None = None

    def _scoped_schema():
        nonlocal _scope_cache
        if _scope_cache is None:
            full = _get_full_schema_from_original(app)
            _scope_cache = _build_filtered_schema(
                full, include_prefixes=[scope], title_suffix=title
            )
        return _scope_cache

    @app.get(openapi_path, include_in_schema=False)
    def scoped_openapi():
        return _scoped_schema()

    @app.get(swagger_path, include_in_schema=False)
    def scoped_swagger():
        return get_swagger_ui_html(openapi_url=openapi_path, title=f"{title} • Swagger")

    @app.get(redoc_path, include_in_schema=False)
    def scoped_redoc():
        return get_redoc_html(openapi_url=openapi_path, title=f"{title} • ReDoc")

    DOC_SCOPES.append((scope, swagger_path, redoc_path, openapi_path, title))

    if auto_exclude_from_root:
        _ensure_root_excludes_registered_scopes(app)


def replace_root_openapi_with_exclusions(app: FastAPI, *, exclude_prefixes: List[str]) -> None:
    """
    Manual hook: make ROOT /openapi.json exclude `exclude_prefixes`.
    Typically not needed because add_prefixed_docs() registers scopes automatically.
    """
    _install_root_filter(app, exclude_prefixes)
