from __future__ import annotations

import types

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.apf_payments.provider.base import ProviderAdapter
from svc_infra.api.fastapi.apf_payments.router import get_service
from svc_infra.api.fastapi.apf_payments.setup import add_payments

# -------------------- App + client --------------------


@pytest_asyncio.fixture
async def app(fake_adapter, mocker) -> FastAPI:
    app = FastAPI()

    # Add error handlers to handle RuntimeError and other exceptions
    from svc_infra.api.fastapi.middleware.errors.catchall import (
        CatchAllExceptionMiddleware,
    )
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
    from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware

    app.add_middleware(CatchAllExceptionMiddleware)
    app.add_middleware(IdempotencyMiddleware, store={})  # Use in-memory store for tests
    register_error_handlers(app)

    # Register ONLY our fake adapter so the registry returns it (incl. webhooks)
    add_payments(
        app,
        register_default_providers=False,
        adapters=[fake_adapter],
    )

    # Minimal session used by routes
    class _DummySession:
        async def flush(self):  # no-op
            return None

        async def execute(self, query):
            # Return a mock result for any database queries
            class _MockResult:
                def scalars(self):
                    return self

                def all(self):
                    return []

                def __iter__(self):
                    return iter([])

            return _MockResult()

    # Proxy service that forwards unknown attrs/methods to the adapter
    class _SvcProxy:
        def __init__(self, adapter: ProviderAdapter):
            self.adapter = adapter
            self.session = _DummySession()

        async def get_customer(self, provider_customer_id: str):
            """Handle get_customer with proper None checking like the real service"""
            out = await self.adapter.get_customer(provider_customer_id)
            if out is None:
                raise RuntimeError("Customer not found")
            return out

        def __getattr__(self, name: str):
            # Handle service-specific methods that aren't on the adapter
            if name == "daily_statements_rollup":
                return fake_adapter.daily_statements_rollup
            elif name == "replay_webhooks":
                return fake_adapter.replay_webhooks
            return getattr(self.adapter, name)

    def _svc_override():
        return _SvcProxy(fake_adapter)

    # Dependency override so handlers receive our proxy service
    app.dependency_overrides[get_service] = _svc_override

    # Mock the database session dependency
    from svc_infra.api.fastapi.db.sql.session import get_session

    async def _mock_session():
        return _DummySession()

    app.dependency_overrides[get_session] = _mock_session

    # Mock authentication dependencies - ALL auth guards
    from svc_infra.api.fastapi.auth.security import (
        Principal,
        _current_principal,
        _optional_principal,
        resolve_api_key,
        resolve_bearer_or_cookie_principal,
    )

    # Create a mock user and api key
    mock_user = mocker.Mock()
    mock_user.id = "test-user-id"

    mock_api_key = mocker.Mock()
    mock_api_key.id = "test-api-key-id"

    # Mock principal with both user and api_key for service routes
    async def _mock_principal():
        return Principal(user=mock_user, scopes=[], via="api_key", api_key=mock_api_key)

    async def _mock_optional_principal():
        return Principal(user=mock_user, scopes=[], via="api_key", api_key=mock_api_key)

    async def _mock_resolve_api_key(*args, **kwargs):
        return Principal(user=mock_user, scopes=[], via="api_key", api_key=mock_api_key)

    async def _mock_resolve_bearer_or_cookie(*args, **kwargs):
        return Principal(user=mock_user, scopes=[], via="jwt", api_key=None)

    app.dependency_overrides[_current_principal] = _mock_principal
    app.dependency_overrides[_optional_principal] = _mock_optional_principal
    app.dependency_overrides[resolve_api_key] = _mock_resolve_api_key
    app.dependency_overrides[resolve_bearer_or_cookie_principal] = _mock_resolve_bearer_or_cookie

    return app


@pytest_asyncio.fixture
async def client(app: FastAPI):
    # Provide an async httpx client against the ASGI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# -------------------- Helper functions --------------------


def create_mock_object(mocker, **kwargs):
    """Create a mock object with proper attribute values"""
    mock_obj = mocker.Mock()
    for key, value in kwargs.items():
        setattr(mock_obj, key, value)
    return mock_obj


# -------------------- Fake adapter --------------------


@pytest.fixture
def fake_adapter(mocker) -> ProviderAdapter:
    class _FakeAdapter:
        name = "stripe"
        # intents
        ensure_customer = mocker.AsyncMock()
        create_intent = mocker.AsyncMock()
        confirm_intent = mocker.AsyncMock()
        cancel_intent = mocker.AsyncMock()
        capture_intent = mocker.AsyncMock()
        refund = mocker.AsyncMock()
        hydrate_intent = mocker.AsyncMock()
        list_intents = mocker.AsyncMock()
        get_intent = mocker.AsyncMock()
        # methods
        attach_payment_method = mocker.AsyncMock()
        list_payment_methods = mocker.AsyncMock()
        detach_payment_method = mocker.AsyncMock()
        set_default_payment_method = mocker.AsyncMock()
        get_payment_method = mocker.AsyncMock()
        update_payment_method = mocker.AsyncMock()
        # invoices
        create_invoice = mocker.AsyncMock()
        finalize_invoice = mocker.AsyncMock()
        void_invoice = mocker.AsyncMock()
        pay_invoice = mocker.AsyncMock()
        add_invoice_line_item = mocker.AsyncMock()
        list_invoices = mocker.AsyncMock()
        get_invoice = mocker.AsyncMock()
        preview_invoice = mocker.AsyncMock()
        list_invoice_line_items = mocker.AsyncMock()
        # invoice line items
        # other endpoints used by tests
        verify_and_parse_webhook = mocker.AsyncMock()
        list_disputes = mocker.AsyncMock()
        get_dispute = mocker.AsyncMock()
        submit_dispute_evidence = mocker.AsyncMock()
        get_balance_snapshot = mocker.AsyncMock()
        list_payouts = mocker.AsyncMock()
        get_payout = mocker.AsyncMock()
        create_setup_intent = mocker.AsyncMock()
        confirm_setup_intent = mocker.AsyncMock()
        get_setup_intent = mocker.AsyncMock()
        create_usage_record = mocker.AsyncMock()
        list_usage_records = mocker.AsyncMock()
        get_usage_record = mocker.AsyncMock()
        # webhook handling
        handle_webhook = mocker.AsyncMock()
        # customer management
        list_customers = mocker.AsyncMock()
        get_customer = mocker.AsyncMock()
        # product/price management
        create_product = mocker.AsyncMock()
        get_product = mocker.AsyncMock()
        list_products = mocker.AsyncMock()
        update_product = mocker.AsyncMock()
        create_price = mocker.AsyncMock()
        get_price = mocker.AsyncMock()
        list_prices = mocker.AsyncMock()
        update_price = mocker.AsyncMock()
        # subscription management
        create_subscription = mocker.AsyncMock()
        get_subscription = mocker.AsyncMock()
        list_subscriptions = mocker.AsyncMock()
        update_subscription = mocker.AsyncMock()
        cancel_subscription = mocker.AsyncMock()
        # refund management
        list_refunds = mocker.AsyncMock()
        get_refund = mocker.AsyncMock()
        # setup intents
        resume_intent_after_action = mocker.AsyncMock()
        # webhook replay
        replay_webhooks = mocker.AsyncMock()
        # service methods (not adapter methods)
        daily_statements_rollup = mocker.AsyncMock()

    return mocker.NonCallableMagicMock(spec_set=_FakeAdapter)


# -------------------- Env + Stripe settings shim --------------------


@pytest.fixture(autouse=True)
def _payments_env(monkeypatch):
    """
    1) Force LOCAL env so user/protected routers don't enforce auth in tests.
    2) Provide Stripe-like settings objects with get_secret_value().
    """
    # (1) LOCAL env = permissive auth posture for user/protected routers
    from svc_infra.app import env as env_mod

    monkeypatch.setattr(env_mod, "CURRENT_ENVIRONMENT", env_mod.LOCAL_ENV, raising=False)

    # (2) Stripe settings shim
    from svc_infra.apf_payments.provider import stripe as stripe_mod

    class _Key:
        def __init__(self, v: str):
            self._v = v

        def get_secret_value(self):
            return self._v

    fake_settings = types.SimpleNamespace(
        stripe=types.SimpleNamespace(
            secret_key=_Key("sk_test_123"),
            webhook_secret=_Key("whsec_test"),  # MUST have get_secret_value()
        )
    )
    monkeypatch.setattr(stripe_mod, "get_payments_settings", lambda: fake_settings)
