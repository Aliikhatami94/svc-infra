from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from svc_infra.security.headers import SECURE_DEFAULTS, SecurityHeadersMiddleware

DEFAULT_SESSION_SECRET = "svc-dev-secret-change-me"


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def _normalize_origins(value: Iterable[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
    else:
        parts = [str(v).strip() for v in value]
    return [p for p in parts if p]


def _resolve_cors_origins(
    provided: Iterable[str] | str | None,
    env: Mapping[str, str],
) -> list[str]:
    if provided is not None:
        return _normalize_origins(provided)
    return _normalize_origins(env.get("CORS_ALLOW_ORIGINS"))


def _resolve_allow_credentials(
    allow_credentials: bool,
    env: Mapping[str, str],
) -> bool:
    env_value = _parse_bool(env.get("CORS_ALLOW_CREDENTIALS"))
    if env_value is None:
        return allow_credentials
    # Allow explicit overrides via function arguments.
    if allow_credentials is not True:
        return allow_credentials
    return env_value


def _configure_cors(
    app: FastAPI,
    *,
    cors_origins: Iterable[str] | str | None,
    allow_credentials: bool,
    env: Mapping[str, str],
) -> None:
    origins = _resolve_cors_origins(cors_origins, env)
    if not origins:
        return

    allow_methods = _normalize_origins(env.get("CORS_ALLOW_METHODS")) or ["*"]
    allow_headers = _normalize_origins(env.get("CORS_ALLOW_HEADERS")) or ["*"]

    credentials = _resolve_allow_credentials(allow_credentials, env)

    wildcard_origins = "*" in origins

    cors_kwargs: dict[str, object] = {
        "allow_credentials": credentials,
        "allow_methods": allow_methods,
        "allow_headers": allow_headers,
        "allow_origins": ["*"] if wildcard_origins else origins,
    }
    origin_regex = env.get("CORS_ALLOW_ORIGIN_REGEX")
    if wildcard_origins:
        cors_kwargs["allow_origin_regex"] = origin_regex or ".*"
    else:
        if origin_regex:
            cors_kwargs["allow_origin_regex"] = origin_regex

    app.add_middleware(CORSMiddleware, **cors_kwargs)


def _configure_security_headers(
    app: FastAPI,
    *,
    overrides: dict[str, str] | None,
    enable_hsts_preload: bool | None,
) -> None:
    merged_overrides = dict(overrides or {})
    if enable_hsts_preload is not None:
        current = merged_overrides.get(
            "Strict-Transport-Security",
            SECURE_DEFAULTS["Strict-Transport-Security"],
        )
        directives = [p.strip() for p in current.split(";") if p.strip()]
        directives = [d for d in directives if d.lower() != "preload"]
        if enable_hsts_preload:
            directives.append("preload")
        merged_overrides["Strict-Transport-Security"] = "; ".join(directives)

    app.add_middleware(SecurityHeadersMiddleware, overrides=merged_overrides)


def _should_add_session_middleware(app: FastAPI) -> bool:
    return not any(m.cls is SessionMiddleware for m in app.user_middleware)


def _configure_session_middleware(
    app: FastAPI,
    *,
    env: Mapping[str, str],
    install: bool,
    secret_key: str | None,
    session_cookie: str,
    max_age: int,
    same_site: str,
    https_only: bool | None,
) -> None:
    if not install or not _should_add_session_middleware(app):
        return

    secret = secret_key or env.get("SESSION_SECRET") or DEFAULT_SESSION_SECRET
    https_env = _parse_bool(env.get("SESSION_COOKIE_SECURE"))
    effective_https_only = (
        https_only if https_only is not None else (https_env if https_env is not None else False)
    )
    same_site_env = env.get("SESSION_COOKIE_SAMESITE")
    same_site_value = same_site_env.strip() if same_site_env else same_site

    max_age_env = env.get("SESSION_COOKIE_MAX_AGE_SECONDS")
    try:
        max_age_value = int(max_age_env) if max_age_env is not None else max_age
    except ValueError:
        max_age_value = max_age

    session_cookie_env = env.get("SESSION_COOKIE_NAME")
    session_cookie_value = session_cookie_env.strip() if session_cookie_env else session_cookie

    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        session_cookie=session_cookie_value,
        max_age=max_age_value,
        same_site=same_site_value,
        https_only=effective_https_only,
    )


def add_security(
    app: FastAPI,
    *,
    cors_origins: Iterable[str] | str | None = None,
    headers_overrides: dict[str, str] | None = None,
    allow_credentials: bool = True,
    env: Mapping[str, str] = os.environ,
    enable_hsts_preload: bool | None = None,
    install_session_middleware: bool = False,
    session_secret_key: str | None = None,
    session_cookie_name: str = "svc_session",
    session_cookie_max_age_seconds: int = 4 * 3600,
    session_cookie_samesite: str = "lax",
    session_cookie_https_only: bool | None = None,
) -> None:
    """Install security middlewares with svc-infra defaults."""

    _configure_security_headers(
        app,
        overrides=headers_overrides,
        enable_hsts_preload=enable_hsts_preload,
    )
    _configure_cors(
        app,
        cors_origins=cors_origins,
        allow_credentials=allow_credentials,
        env=env,
    )
    _configure_session_middleware(
        app,
        env=env,
        install=install_session_middleware,
        secret_key=session_secret_key,
        session_cookie=session_cookie_name,
        max_age=session_cookie_max_age_seconds,
        same_site=session_cookie_samesite,
        https_only=session_cookie_https_only,
    )


__all__ = [
    "add_security",
]
