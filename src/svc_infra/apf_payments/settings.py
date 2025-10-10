from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, SecretStr

STRIPE_KEY = os.getenv("STRIPE_SECRET") or os.getenv("STRIPE_API_KEY")
STRIPE_WH = os.getenv("STRIPE_WH_SECRET")
PROVIDER = (os.getenv("APF_PAYMENTS_PROVIDER") or os.getenv("PAYMENTS_PROVIDER", "stripe")).lower()


class StripeConfig(BaseModel):
    secret_key: SecretStr
    webhook_secret: Optional[SecretStr] = None


class AdyenConfig(BaseModel):
    api_key: SecretStr
    client_key: Optional[SecretStr] = None
    merchant_account: Optional[str] = None
    hmac_key: Optional[SecretStr] = None


class PaymentsSettings(BaseModel):
    default_provider: str = PROVIDER

    # optional multi-tenant/provider map hook can be added later
    stripe: Optional[StripeConfig] = (
        StripeConfig(
            secret_key=SecretStr(STRIPE_KEY),
            webhook_secret=SecretStr(STRIPE_WH) if STRIPE_WH else None,
        )
        if STRIPE_KEY
        else None
    )
    adyen: Optional[AdyenConfig] = None


_SETTINGS: Optional[PaymentsSettings] = None


def get_payments_settings() -> PaymentsSettings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = PaymentsSettings()
    return _SETTINGS
