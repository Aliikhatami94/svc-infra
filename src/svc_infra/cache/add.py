from __future__ import annotations

"""
Easy integration helper to wire the cache backend into an ASGI app lifecycle.

Contract:
- Idempotent: multiple calls are safe; startup/shutdown handlers are registered once.
- Env-driven defaults: respects CACHE_URL/REDIS_URL, CACHE_PREFIX, CACHE_VERSION, APP_ENV.
- Lifecycle: registers startup (init + readiness probe) and shutdown (graceful close).
- Ergonomics: exposes the underlying cache instance at app.state.cache by default.

This does not replace the per-function decorators (`cache_read`, `cache_write`) and
does not alter existing direct APIs; it simply standardizes initialization and wiring.
"""

import logging
import os
from typing import Any, Callable, Optional

from svc_infra.cache.backend import DEFAULT_READINESS_TIMEOUT
from svc_infra.cache.backend import instance as _instance
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import shutdown_cache as _shutdown_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

logger = logging.getLogger(__name__)


def _derive_settings(
    url: Optional[str], prefix: Optional[str], version: Optional[str]
) -> tuple[str, str, str]:
    """Derive cache settings from parameters or environment variables.

    Precedence:
      - explicit function arguments
      - environment variables (CACHE_URL/REDIS_URL, CACHE_PREFIX, CACHE_VERSION)
      - sensible defaults (mem://, "svc", "v1")
    """

    derived_url = url or os.getenv("CACHE_URL") or os.getenv("REDIS_URL") or "mem://"
    derived_prefix = prefix or os.getenv("CACHE_PREFIX") or "svc"
    derived_version = version or os.getenv("CACHE_VERSION") or "v1"
    return derived_url, derived_prefix, derived_version


def add_cache(
    app: Any | None = None,
    *,
    url: str | None = None,
    prefix: str | None = None,
    version: str | None = None,
    readiness_timeout: float | None = None,
    expose_state: bool = True,
    state_key: str = "cache",
) -> Callable[[], None]:
    """Wire cache initialization and lifecycle into the ASGI app.

    If an app is provided, registers startup/shutdown handlers. Otherwise performs
    immediate initialization (best-effort) without awaiting readiness.

    Returns a no-op shutdown callable for API symmetry with other helpers.
    """

    # Compute effective settings
    eff_url, eff_prefix, eff_version = _derive_settings(url, prefix, version)

    # If no app provided, do a simple init and return
    if app is None:
        try:
            _setup_cache(url=eff_url, prefix=eff_prefix, version=eff_version)
            logger.info(
                "Cache initialized (no app wiring): backend=%s namespace=%s",
                eff_url,
                f"{eff_prefix}:{eff_version}",
            )
        except Exception:
            logger.exception("Cache initialization failed (no app wiring)")
        return lambda: None

    # Idempotence: avoid duplicate wiring
    try:
        state = getattr(app, "state", None)
        already = bool(getattr(state, "_svc_cache_wired", False))
    except Exception:
        state = None
        already = False

    if already:
        logger.debug("add_cache: app already wired; skipping re-registration")
        return lambda: None

    # Define lifecycle handlers
    async def _startup():
        _setup_cache(url=eff_url, prefix=eff_prefix, version=eff_version)
        try:
            await _wait_ready(timeout=readiness_timeout or DEFAULT_READINESS_TIMEOUT)
        except Exception:
            # Bubble up to fail fast on startup; tests and prod prefer visibility
            logger.exception("Cache readiness probe failed during startup")
            raise
        # Expose cache instance for convenience
        if expose_state and hasattr(app, "state"):
            try:
                setattr(app.state, state_key, _instance())
            except Exception:
                logger.debug("Unable to expose cache instance on app.state", exc_info=True)

    async def _shutdown():
        try:
            await _shutdown_cache()
        except Exception:
            # Best-effort; shutdown should not crash the app
            logger.debug("Cache shutdown encountered errors (ignored)", exc_info=True)

    # Register event handlers when supported
    register_ok = False
    try:
        if hasattr(app, "add_event_handler"):
            app.add_event_handler("startup", _startup)
            app.add_event_handler("shutdown", _shutdown)
            register_ok = True
    except Exception:
        register_ok = False

    if not register_ok:
        # Fallback: attempt FastAPI/Starlette .on_event decorators dynamically
        try:
            on_event = getattr(app, "on_event", None)
            if callable(on_event):
                on_event("startup")(_startup)  # type: ignore[misc]
                on_event("shutdown")(_shutdown)  # type: ignore[misc]
                register_ok = True
        except Exception:
            register_ok = False

    # Mark wired and expose state immediately if desired
    if hasattr(app, "state"):
        try:
            setattr(app.state, "_svc_cache_wired", True)
            if expose_state and not hasattr(app.state, state_key):
                setattr(app.state, state_key, _instance())
        except Exception:
            pass

    if register_ok:
        logger.info("Cache wired: url=%s namespace=%s", eff_url, f"{eff_prefix}:{eff_version}")
    else:
        # If we cannot register handlers, at least initialize now
        try:
            _setup_cache(url=eff_url, prefix=eff_prefix, version=eff_version)
        except Exception:
            logger.exception("Cache initialization failed (no event registration)")

    # Return a simple shutdown handle for symmetry with other add_* helpers
    return lambda: None


__all__ = ["add_cache"]
