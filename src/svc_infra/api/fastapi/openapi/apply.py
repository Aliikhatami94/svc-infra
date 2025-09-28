from typing import Any, Callable

from svc_infra.api.fastapi.dual.router import DualAPIRouter


def apply_default_security(router: DualAPIRouter, default_security: list[dict] | None) -> None:
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


def apply_default_responses(router: DualAPIRouter, defaults: dict[int, dict]) -> None:
    """Automatically add standard error responses if the route didn't override them."""
    original_add = router.add_api_route

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        resp = kwargs.get("responses") or {}
        # only add codes that aren't already present
        for code, spec in defaults.items():
            resp.setdefault(code, spec)
        kwargs["responses"] = resp
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]
