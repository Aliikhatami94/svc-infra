from __future__ import annotations

import logging
from typing import Iterable, Optional

from fastapi import FastAPI

from svc_infra.apf_payments.provider.registry import get_provider_registry
from svc_infra.api.fastapi.apf_payments.router import build_payments_routers

logger = logging.getLogger(__name__)


def _maybe_register_default_providers(
    register_defaults: bool, adapters: Optional[Iterable[object]]
):
    reg = get_provider_registry()
    if register_defaults:
        # Try Stripe by default; silently skip if not configured
        try:
            from svc_infra.apf_payments.provider.stripe import StripeAdapter

            reg.register(StripeAdapter())
        except Exception:
            pass
        try:
            from svc_infra.apf_payments.provider.aiydan import AiydanAdapter

            reg.register(AiydanAdapter())
        except Exception:
            pass
    if adapters:
        for a in adapters:
            reg.register(a)  # must implement ProviderAdapter protocol (name, create_intent, etc.)


def add_payments(
    app: FastAPI,
    *,
    prefix: str = "/payments",
    register_default_providers: bool = True,
    adapters: Optional[Iterable[object]] = None,
    include_in_docs: bool | None = None,  # None = keep your env-based default visibility
) -> None:
    """
    One-call payments installer.

    - Registers provider adapters (defaults + any provided).
    - Mounts all Payments routers (user/protected/service/public) under `prefix`.
    - Reuses your OpenAPI defaults (security + responses) via DualAPIRouter factories.
    """
    _maybe_register_default_providers(register_default_providers, adapters)

    for r in build_payments_routers(prefix=prefix):
        app.include_router(
            r, include_in_schema=True if include_in_docs is None else bool(include_in_docs)
        )

    # Store the startup function to be called by lifespan if needed
    async def _payments_startup_check():
        try:
            reg = get_provider_registry()
            adapter = reg.get()  # default provider
            # Try a cheap call (Stripe: read account or key balance; we just access .name)
            _ = adapter.name
        except Exception as e:
            # Log loud; don't crash the whole app by default
            logger.warning(f"[payments] Provider adapter not ready: {e}")

    # Add to app state for potential lifespan usage
    if not hasattr(app.state, "startup_events"):
        app.state.startup_events = []
    app.state.startup_events.append(_payments_startup_check)
