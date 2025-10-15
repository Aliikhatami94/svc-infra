from __future__ import annotations

"""
Lightweight metrics hooks for abuse heuristics. Intentionally minimal to avoid pulling
full metrics stacks; these are no-ops by default but can be swapped in tests or wired
to a metrics backend by overriding the functions.
"""

from typing import Callable, Optional

# Function variables so applications/tests can replace them at runtime.
on_rate_limit_exceeded: Callable[[str, int, int], None] | None = None
"""
Called when a request is rate-limited.
Args:
    key: identifier used for rate limiting (e.g., API key or IP)
    limit: configured limit for the window
    retry_after: seconds until next allowed attempt
"""

on_suspect_payload: Callable[[Optional[str], int], None] | None = None
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


def emit_suspect_payload(path: Optional[str], size: int) -> None:
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
