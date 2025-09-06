# Lazy package init to avoid side effects at import time.
# Submodules (e.g., oauth_router) can be imported directly via `from svc_infra.auth import oauth_router`.

__all__ = ["auth_to_fastapi"]


def __getattr__(name: str):
    if name == "auth_to_fastapi":
        from .integration import include_auth as auth_to_fastapi  # noqa: WPS433 (local import)
        return auth_to_fastapi
    raise AttributeError(name)
