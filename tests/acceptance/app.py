from __future__ import annotations

import os
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.apf_payments.provider.base import ProviderAdapter
from svc_infra.apf_payments.schemas import (
    CustomerOut,
    CustomerUpsertIn,
    IntentCreateIn,
    IntentOut,
    PaymentMethodAttachIn,
    PaymentMethodOut,
)
from svc_infra.api.fastapi.apf_payments.setup import add_payments
from svc_infra.api.fastapi.auth.security import Principal, _current_principal
from svc_infra.api.fastapi.db.sql.add import add_sql_db
from svc_infra.api.fastapi.ease import easy_service_app
from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

# Minimal acceptance app wiring the library's routers and defaults
app = easy_service_app(
    name="svc-infra-acceptance",
    release="A0",
    versions=[
        ("v1", "svc_infra.api.fastapi.routers", None),
    ],
    root_routers=["svc_infra.api.fastapi.routers"],
    public_cors_origins=["*"],
    root_public_base_url="/",
)

# Wire SQL session: prefer env DATABASE_URL, else default to a local SQLite file for acceptance.
db_url = os.getenv("DATABASE_URL") or "sqlite+aiosqlite:////tmp/acceptance.db"
add_sql_db(app, url=db_url)


# Minimal auth users table to satisfy FK references from payments models.
class _AcceptUser(ModelBase):
    __tablename__ = "users"
    __svc_infra_auth_user__ = True  # let authref discover this as the auth user model

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)


# Auto-create schema at startup (payments models + minimal users table).
@app.on_event("startup")
async def _acceptance_create_schema() -> None:  # noqa: D401
    # Import payments models so they register on ModelBase.metadata
    from svc_infra.apf_payments import models as _pay_models  # noqa: F401

    engine = create_async_engine(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(ModelBase.metadata.create_all)
    finally:
        await engine.dispose()


# Minimal fake payments adapter for acceptance (no external calls).
class FakeAdapter(ProviderAdapter):
    name = "fake"

    def __init__(self):
        self._customers: dict[str, CustomerOut] = {}
        self._methods: dict[str, list[PaymentMethodOut]] = {}
        self._intents: dict[str, IntentOut] = {}

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:  # type: ignore[override]
        cid = data.email or data.name or "cus_accept"
        out = CustomerOut(
            id=cid, provider=self.name, provider_customer_id=cid, email=data.email, name=data.name
        )
        self._customers[cid] = out
        self._methods.setdefault(cid, [])
        return out

    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:  # type: ignore[override]
        mid = f"pm_{len(self._methods.get(data.customer_provider_id, [])) + 1}"
        out = PaymentMethodOut(
            id=mid,
            provider=self.name,
            provider_customer_id=data.customer_provider_id,
            provider_method_id=mid,
            brand="visa",
            last4="4242",
            exp_month=1,
            exp_year=2030,
            is_default=bool(data.make_default),
        )
        lst = self._methods.setdefault(data.customer_provider_id, [])
        if data.make_default:
            # clear existing default
            for m in lst:
                m.is_default = False
        lst.append(out)
        return out

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:  # type: ignore[override]
        return list(self._methods.get(provider_customer_id, []))

    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:  # type: ignore[override]
        iid = f"pi_{len(self._intents) + 1}"
        out = IntentOut(
            id=iid,
            provider=self.name,
            provider_intent_id=iid,
            status="requires_confirmation",
            amount=data.amount,
            currency=data.currency,
            client_secret=f"secret_{iid}",
        )
        self._intents[iid] = out
        return out

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:  # type: ignore[override]
        return self._intents[provider_intent_id]

    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:  # type: ignore[override]
        for methods in self._methods.values():
            for m in methods:
                if m.provider_method_id == provider_method_id:
                    return m
        raise KeyError(provider_method_id)

    async def update_payment_method(self, provider_method_id: str, data):  # type: ignore[override]
        m = await self.get_payment_method(provider_method_id)
        return m

    async def get_intent(self, provider_intent_id: str) -> IntentOut:  # non-protocol helper
        return await self.hydrate_intent(provider_intent_id)


# Install payments under /payments using the fake adapter (skip default provider registration).
add_payments(app, prefix="/payments", register_default_providers=False, adapters=[FakeAdapter()])


# Override auth to always provide a user with a tenant for acceptance.
def _accept_principal():
    return Principal(user=SimpleNamespace(tenant_id="accept-tenant"), scopes=["*"], via="jwt")


app.dependency_overrides[_current_principal] = _accept_principal
