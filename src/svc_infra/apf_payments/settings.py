from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, SecretStr


class StripeConfig(BaseModel):
    secret_key: SecretStr
    webhook_secret: Optional[SecretStr] = None


class AdyenConfig(BaseModel):
    api_key: SecretStr
    client_key: Optional[SecretStr] = None
    merchant_account: Optional[str] = None
    hmac_key: Optional[SecretStr] = None


class PaymentsSettings(BaseModel):
    default_provider: str = os.getenv("PAYMENTS_PROVIDER", "stripe").lower()
    # optional multi-tenant/provider map hook can be added later
    stripe: Optional[StripeConfig] = (
        StripeConfig(
            secret_key=SecretStr(os.getenv("STRIPE_SECRET", "")),
            webhook_secret=SecretStr(os.getenv("STRIPE_WH_SECRET", "")),
        )
        if os.getenv("STRIPE_SECRET")
        else None
    )
    adyen: Optional[AdyenConfig] = None  # fill from env if you want


_SETTINGS: Optional[PaymentsSettings] = None


def get_payments_settings() -> PaymentsSettings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = PaymentsSettings()
    return _SETTINGS
