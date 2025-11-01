from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from svc_infra.app.env import pick


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_default_timeout_seconds() -> float:
    """Return default outbound HTTP client timeout in seconds.

    Env var: HTTP_CLIENT_TIMEOUT_SECONDS (float)
    Defaults: 10.0 seconds for all envs unless overridden; tweakable via pick() if needed.
    """
    default = pick(prod=10.0, nonprod=10.0)
    return _parse_float_env("HTTP_CLIENT_TIMEOUT_SECONDS", default)


def make_timeout(seconds: float | None = None) -> httpx.Timeout:
    s = seconds if seconds is not None else get_default_timeout_seconds()
    # Apply same timeout for connect/read/write/pool for simplicity
    return httpx.Timeout(timeout=s)


def new_httpx_client(
    *,
    timeout_seconds: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
    base_url: Optional[str] = None,
    **kwargs: Any,
) -> httpx.Client:
    """Create a sync httpx Client with default timeout and optional headers/base_url.

    Callers can override timeout_seconds; remaining kwargs are forwarded to httpx.Client.
    """
    timeout = make_timeout(timeout_seconds)
    # httpx doesn't accept base_url=None; only pass if non-None
    client_kwargs = {"timeout": timeout, "headers": headers, **kwargs}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    return httpx.Client(**client_kwargs)


def new_async_httpx_client(
    *,
    timeout_seconds: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
    base_url: Optional[str] = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create an async httpx AsyncClient with default timeout and optional headers/base_url.

    Callers can override timeout_seconds; remaining kwargs are forwarded to httpx.AsyncClient.
    """
    timeout = make_timeout(timeout_seconds)
    # httpx doesn't accept base_url=None; only pass if non-None
    client_kwargs = {"timeout": timeout, "headers": headers, **kwargs}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    return httpx.AsyncClient(**client_kwargs)
