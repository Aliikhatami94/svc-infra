from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, SecretStr

STRIPE_KEY = os.getenv("STRIPE_SECRET") or os.getenv("STRIPE_API_KEY")
STRIPE_WH = os.getenv("STRIPE_WH_SECRET")
PROVIDER = (os.getenv("APF_PAYMENTS_PROVIDER") or os.getenv("PAYMENTS_PROVIDER", "stripe")).lower()

AIYDAN_KEY = os.getenv("AIYDAN_API_KEY")
AIYDAN_CLIENT_KEY = os.getenv("AIYDAN_CLIENT_KEY")
AIYDAN_MERCHANT = os.getenv("AIYDAN_MERCHANT_ACCOUNT")
AIYDAN_HMAC = os.getenv("AIYDAN_HMAC_KEY")
AIYDAN_BASE_URL = os.getenv("AIYDAN_BASE_URL")
AIYDAN_WH = os.getenv("AIYDAN_WH_SECRET")


class StripeConfig(BaseModel):
    secret_key: SecretStr
    webhook_secret: Optional[SecretStr] = None


class AiydanConfig(BaseModel):
    api_key: SecretStr
    client_key: Optional[SecretStr] = None
    merchant_account: Optional[str] = None
    hmac_key: Optional[SecretStr] = None
    base_url: Optional[str] = None
    webhook_secret: Optional[SecretStr] = None


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
    aiydan: Optional[AiydanConfig] = (
        AiydanConfig(
            api_key=SecretStr(AIYDAN_KEY),
            client_key=SecretStr(AIYDAN_CLIENT_KEY) if AIYDAN_CLIENT_KEY else None,
            merchant_account=AIYDAN_MERCHANT,
            hmac_key=SecretStr(AIYDAN_HMAC) if AIYDAN_HMAC else None,
            base_url=AIYDAN_BASE_URL,
            webhook_secret=SecretStr(AIYDAN_WH) if AIYDAN_WH else None,
        )
        if AIYDAN_KEY
        else None
    )


_SETTINGS: Optional[PaymentsSettings] = None


def get_payments_settings() -> PaymentsSettings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = PaymentsSettings()
    return _SETTINGS
