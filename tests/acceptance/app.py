from __future__ import annotations

import os
from types import SimpleNamespace

from sqlalchemy import create_engine

from svc_infra.apf_payments import settings as payments_settings
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
from svc_infra.api.fastapi.db.sql.session import get_session
from svc_infra.api.fastapi.ease import EasyAppOptions, ObservabilityOptions, easy_service_app

# Minimal acceptance app wiring the library's routers and defaults
os.environ.setdefault("PAYMENTS_PROVIDER", "fake")

payments_settings._SETTINGS = payments_settings.PaymentsSettings(default_provider="fake")
# Provide a tiny SQLite engine so db_pool_* metrics are bound during acceptance
_engine = create_engine("sqlite:///:memory:")
# Trigger a connection once so pool metrics initialize label series
try:
    with _engine.connect() as _conn:
        _ = _conn.execute("SELECT 1")
except Exception:
    # best effort; tests don't rely on actual DB
    pass

app = easy_service_app(
    name="svc-infra-acceptance",
    release="A0",
    versions=[
        ("v1", "svc_infra.api.fastapi.routers", None),
    ],
    root_routers=["svc_infra.api.fastapi.routers"],
    public_cors_origins=["*"],
    root_public_base_url="/",
    options=EasyAppOptions(
        observability=ObservabilityOptions(
            enable=True,
            db_engines=[_engine],
            metrics_path="/metrics",
        )
    ),
)


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


# Replace the DB session dependency with a no-op stub so tests stay self-contained.
class _StubScalarResult:
    def __init__(self, rows: list | None = None):
        self._rows = rows or []

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):  # pragma: no cover - best effort stub behaviour
        if not self._rows:
            raise ValueError("No rows available")
        if len(self._rows) > 1:
            raise ValueError("Multiple rows available")
        return self._rows[0]


class _StubResult(_StubScalarResult):
    def scalars(self):
        return _StubScalarResult(self._rows)


class _StubSession:
    async def execute(self, _statement):
        return _StubResult([])

    async def scalar(self, _statement):
        return None

    def add(self, _obj):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


async def _stub_get_session():
    yield _StubSession()


app.dependency_overrides[get_session] = _stub_get_session


# Override auth to always provide a user with a tenant for acceptance.
def _accept_principal():
    return Principal(user=SimpleNamespace(tenant_id="accept-tenant"), scopes=["*"], via="jwt")


app.dependency_overrides[_current_principal] = _accept_principal
