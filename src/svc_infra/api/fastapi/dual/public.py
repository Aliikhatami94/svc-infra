from __future__ import annotations

from typing import Any

from svc_infra.api.fastapi.dual.router import DualAPIRouter


def public_router(**kwargs: Any) -> DualAPIRouter:
    """
    Public router: absolutely NO auth dependencies.
    Automatically marks operations as public in OpenAPI (no lock icon).
    """
    r = DualAPIRouter(**kwargs)

    original_add = r.add_api_route

    def _wrapped_add_api_route(path: str, endpoint, **kw: Any):
        ox = kw.get("openapi_extra") or {}
        if "security" not in ox:
            ox["security"] = []  # explicit: public
            kw["openapi_extra"] = ox
        return original_add(path, endpoint, **kw)

    r.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]
    return r
