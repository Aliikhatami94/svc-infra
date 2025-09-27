from __future__ import annotations

from typing import Optional

from starlette.requests import Request

from svc_infra.app.env import IS_PROD

from .settings import get_auth_settings


def _is_local_host(host: str) -> bool:
    h = (host or "").split(":")[0].lower()
    return h in {"localhost", "127.0.0.1", "::1"} or h.endswith(".localhost")


def _is_https(request: Request) -> bool:
    proto = (
        (request.headers.get("x-forwarded-proto") or request.url.scheme or "").split(",")[0].strip()
    )
    return proto.lower() == "https"


def compute_cookie_params(request: Request, *, name: str) -> dict:
    st = get_auth_settings()
    cfg_domain = (getattr(st, "session_cookie_domain", "") or "").strip()

    domain: Optional[str] = None
    if cfg_domain and not _is_local_host(cfg_domain):
        domain = cfg_domain

    explicit_secure = getattr(st, "session_cookie_secure", None)
    secure = (
        bool(explicit_secure) if explicit_secure is not None else (_is_https(request) or IS_PROD)
    )

    samesite = str(getattr(st, "session_cookie_samesite", "lax")).lower()
    max_age = int(getattr(st, "session_cookie_max_age_seconds", 4 * 3600))

    return {
        "key": name,
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "domain": domain,
        "path": "/",
        "max_age": max_age,
    }
