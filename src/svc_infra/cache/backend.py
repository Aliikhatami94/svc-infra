from __future__ import annotations

from typing import Optional

from cashews import cache as _cache

_current_prefix: str = "svc"
_current_version: str = "v1"


def alias() -> str:
    """Human-readable namespace label."""
    return f"{_current_prefix}:{_current_version}"


def _full_prefix() -> str:
    """Actual key prefix applied by cashews."""
    return f"{_current_prefix}:{_current_version}:"


def setup_cache(
    url: Optional[str] = None,
    *,
    prefix: Optional[str] = None,
    version: Optional[str] = None,
):
    """
    Configure Cashews and set a global key prefix so keys are namespaced by
    {prefix}:{version}:  e.g.  apiframeworks-api:vdev:
    Returned value is awaitable (Cashews’ setup), so callers may await or not.
    """
    global _current_prefix, _current_version

    if prefix:
        _current_prefix = prefix
    if version:
        _current_version = version

    # Setup backend (awaitable)
    setup_awaitable = _cache.setup(url) if url else _cache.setup()

    # ★ The important line: make the namespace real
    if hasattr(_cache, "set_prefix"):
        _cache.set_prefix(_full_prefix())

    return setup_awaitable  # callers can await or not


async def wait_ready(timeout: float = 5.0) -> None:
    probe_key = f"{_full_prefix()}__probe__"
    await _cache.set(probe_key, "ok", expire=3)
    ok = await _cache.get(probe_key)
    if ok != "ok":
        raise RuntimeError("cache readiness probe failed")


async def shutdown_cache() -> None:
    try:
        await _cache.close()
    except Exception:
        pass


def instance():
    return _cache
