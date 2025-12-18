from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

import httpx

from svc_infra.app.env import pick

# Context var for request ID propagation across async boundaries
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    """Set the current request ID for propagation to outbound HTTP calls."""
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    """Get the current request ID for propagation."""
    return _request_id_ctx.get()


def _merge_request_id_header(headers: dict[str, str] | None) -> dict[str, str]:
    """Merge X-Request-Id header into headers dict if request ID is set."""
    result = dict(headers) if headers else {}
    request_id = get_request_id()
    if request_id and "X-Request-Id" not in result:
        result["X-Request-Id"] = request_id
    return result


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
    timeout_seconds: float | None = None,
    headers: dict[str, str] | None = None,
    base_url: str | None = None,
    propagate_request_id: bool = True,
    **kwargs: Any,
) -> httpx.Client:
    """Create a sync httpx Client with default timeout and optional headers/base_url.

    Callers can override timeout_seconds; remaining kwargs are forwarded to httpx.Client.
    If propagate_request_id=True (default), X-Request-Id header is added from context.
    """
    timeout = make_timeout(timeout_seconds)
    merged_headers = _merge_request_id_header(headers) if propagate_request_id else headers
    # httpx doesn't accept base_url=None; only pass if non-None
    client_kwargs = {"timeout": timeout, "headers": merged_headers, **kwargs}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    return httpx.Client(**client_kwargs)


def new_async_httpx_client(
    *,
    timeout_seconds: float | None = None,
    headers: dict[str, str] | None = None,
    base_url: str | None = None,
    propagate_request_id: bool = True,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create an async httpx AsyncClient with default timeout and optional headers/base_url.

    Callers can override timeout_seconds; remaining kwargs are forwarded to httpx.AsyncClient.
    If propagate_request_id=True (default), X-Request-Id header is added from context.
    """
    timeout = make_timeout(timeout_seconds)
    merged_headers = _merge_request_id_header(headers) if propagate_request_id else headers
    # httpx doesn't accept base_url=None; only pass if non-None
    client_kwargs = {"timeout": timeout, "headers": merged_headers, **kwargs}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    return httpx.AsyncClient(**client_kwargs)
