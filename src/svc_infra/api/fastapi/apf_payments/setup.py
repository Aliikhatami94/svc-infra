from __future__ import annotations

from typing import Iterable, Optional

from fastapi import FastAPI

from svc_infra.apf_payments.provider.registry import get_provider_registry
from svc_infra.api.fastapi.apf_payments.router import build_payments_routers


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
