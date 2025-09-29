from __future__ import annotations

from fastapi import FastAPI

from .mutators import auth_mutator
from .pipeline import apply_mutators


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
    apply_mutators(app, auth_mutator(include_api_key))
