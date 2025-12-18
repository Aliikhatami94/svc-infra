from __future__ import annotations

import os

from pydantic import BaseModel, SecretStr

STRIPE_KEY = os.getenv("STRIPE_SECRET") or os.getenv("STRIPE_API_KEY")
STRIPE_WH = os.getenv("STRIPE_WH_SECRET")
PROVIDER = (
    os.getenv("APF_PAYMENTS_PROVIDER") or os.getenv("PAYMENTS_PROVIDER", "stripe") or "stripe"
).lower()

AIYDAN_KEY = os.getenv("AIYDAN_API_KEY")
AIYDAN_CLIENT_KEY = os.getenv("AIYDAN_CLIENT_KEY")
AIYDAN_MERCHANT = os.getenv("AIYDAN_MERCHANT_ACCOUNT")
AIYDAN_HMAC = os.getenv("AIYDAN_HMAC_KEY")
AIYDAN_BASE_URL = os.getenv("AIYDAN_BASE_URL")
AIYDAN_WH = os.getenv("AIYDAN_WH_SECRET")


class StripeConfig(BaseModel):
    secret_key: SecretStr
    webhook_secret: SecretStr | None = None


class AiydanConfig(BaseModel):
    api_key: SecretStr
    client_key: SecretStr | None = None
    merchant_account: str | None = None
    hmac_key: SecretStr | None = None
    base_url: str | None = None
    webhook_secret: SecretStr | None = None


class PaymentsSettings(BaseModel):
    default_provider: str = PROVIDER

    # optional multi-tenant/provider map hook can be added later
    stripe: StripeConfig | None = (
        StripeConfig(
            secret_key=SecretStr(STRIPE_KEY),
            webhook_secret=SecretStr(STRIPE_WH) if STRIPE_WH else None,
        )
        if STRIPE_KEY
        else None
    )
    aiydan: AiydanConfig | None = (
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


_SETTINGS: PaymentsSettings | None = None


def get_payments_settings() -> PaymentsSettings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = PaymentsSettings()
    return _SETTINGS
