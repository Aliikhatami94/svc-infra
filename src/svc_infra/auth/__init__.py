from __future__ import annotations


# Lazy exports to avoid importing optional or heavy submodules at package import time.
# Accessing these attributes will import the underlying implementations on demand.

def __getattr__(name: str):
    if name == "include_auth":
        from .include_auth import include_auth as _f

        return _f
    if name == "get_fastapi_users":
        from .users import get_fastapi_users as _f

        return _f
    if name == "oauth_router":
        from .oauth_router import oauth_router as _f

        return _f
    if name == "get_auth_settings":
        # This module may not exist in consumer projects until scaffolded.
        from .settings import get_auth_settings as _f  # type: ignore

        return _f
    raise AttributeError(f"module 'svc_infra.auth' has no attribute {name!r}")
