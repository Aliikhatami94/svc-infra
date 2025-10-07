from __future__ import annotations

from svc_infra.apf_payments.provider.registry import get_provider_registry
from svc_infra.apf_payments.provider.stripe import StripeAdapter


def register_default_payment_adapters():
    reg = get_provider_registry()
    try:
        reg.register(StripeAdapter())
    except Exception:
        # Stripe may be optional; ignore if not configured
        pass
