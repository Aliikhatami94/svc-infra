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

    def _only_ref(obj: dict) -> dict:
        # If someone passed {"description": "...", "$ref": "..."} normalize to only {"$ref": "..."}
        return {"$ref": obj["$ref"]} if isinstance(obj, dict) and "$ref" in obj else obj

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        responses = {**(kwargs.get("responses") or {})}
        for code, ref in (defaults or {}).items():
            responses.setdefault(str(code), _only_ref(ref))
        # Also normalize any explicitly-specified refs on this operation
        for code, resp in list(responses.items()):
            if isinstance(resp, dict) and "$ref" in resp and len(resp) > 1:
                responses[code] = {"$ref": resp["$ref"]}
        kwargs["responses"] = responses
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]
