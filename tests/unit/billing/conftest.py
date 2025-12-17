from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.billing.setup import add_billing


@pytest_asyncio.fixture
async def app(mocker) -> FastAPI:
    app = FastAPI()

    # Error handling and idempotency middleware similar to payments tests
    from svc_infra.api.fastapi.middleware.errors.catchall import (
        CatchAllExceptionMiddleware,
    )
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
    from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware

    app.add_middleware(CatchAllExceptionMiddleware)
    app.add_middleware(IdempotencyMiddleware, store={})
    register_error_handlers(app)

    # Mount billing router
    add_billing(app)

    # Override DB session dependency with a dummy async session for handler compatibility
    class _DummySession:
        async def execute(self, *_, **__):
            class _Res:
                def scalars(self):
                    return self

                def all(self):
                    return []

                def scalar_one_or_none(self):
                    return None

            return _Res()

        async def flush(self):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

    from svc_infra.api.fastapi.db.sql.session import get_session

    async def _mock_session():
        return _DummySession()

    app.dependency_overrides[get_session] = _mock_session

    # Override service dependency to avoid DB and assert call parameters
    from svc_infra.api.fastapi.billing.router import get_service

    class _FakeSvc:
        async def record_usage(self, *, metric, amount, at, idempotency_key, metadata):
            # return a stable id for test
            return "evt_test_1"

        async def list_daily_aggregates(self, *, metric, date_from, date_to):
            class Row:
                def __init__(self, ps, g, m, t):
                    self.period_start = ps
                    self.granularity = g
                    self.metric = m
                    self.total = t

            return []

    def _svc_override():
        return _FakeSvc()

    app.dependency_overrides[get_service] = _svc_override

    # Tenant and auth overrides: provide a static tenant id
    from svc_infra.api.fastapi.tenancy.context import require_tenant_id

    async def _tenant():
        return "t_test"

    app.dependency_overrides[require_tenant_id] = _tenant

    return app


@pytest_asyncio.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
