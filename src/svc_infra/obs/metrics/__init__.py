"""Metrics package public API.

Provides lightweight, overridable hooks for abuse heuristics so callers can
plug in logging or a metrics backend without a hard dependency.
"""

from __future__ import annotations

from collections.abc import Callable

# Function variables so applications/tests can replace them at runtime.
on_rate_limit_exceeded: Callable[[str, int, int], None] | None = None
"""
Called when a request is rate-limited.
Args:
    key: identifier used for rate limiting (e.g., API key or IP)
    limit: configured limit for the window
    retry_after: seconds until next allowed attempt
"""

on_suspect_payload: Callable[[str | None, int], None] | None = None
"""
Called when a request exceeds the configured size limit.
Args:
    path: request path if available
    size: reported content-length
"""


def emit_rate_limited(key: str, limit: int, retry_after: int) -> None:
    if on_rate_limit_exceeded:
        try:
            on_rate_limit_exceeded(key, limit, retry_after)
        except Exception:
            # Never break request flow on metrics exceptions
            pass


def emit_suspect_payload(path: str | None, size: int) -> None:
    if on_suspect_payload:
        try:
            on_suspect_payload(path, size)
        except Exception:
            pass


__all__ = [
    "emit_rate_limited",
    "emit_suspect_payload",
    "on_rate_limit_exceeded",
    "on_suspect_payload",
]
