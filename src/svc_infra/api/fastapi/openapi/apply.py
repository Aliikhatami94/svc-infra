from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter


def apply_default_security(router: APIRouter, *, default_security: list[dict] | None) -> None:
    if default_security is None:
        return
    original_add = router.add_api_route

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        ox = kwargs.get("openapi_extra") or {}
        if "security" not in ox:
            ox["security"] = default_security
            kwargs["openapi_extra"] = ox
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]


def apply_default_responses(router: APIRouter, defaults: dict[int, dict]) -> None:
    original_add = router.add_api_route

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        responses = kwargs.get("responses") or {}
        # don't clobber explicit codes; only fill gaps
        for code, ref in (defaults or {}).items():
            responses.setdefault(str(code), ref)
        kwargs["responses"] = responses
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]
