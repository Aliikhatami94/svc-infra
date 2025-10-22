from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.billing.quotas import require_quota


@pytest.mark.asyncio
async def test_quota_dependency_allows_without_subscription(mocker):
    app = FastAPI()

    # Override dependencies to simulate no subscription and no aggregates
    from svc_infra.api.fastapi.db.sql.session import get_session
    from svc_infra.api.fastapi.tenancy.context import require_tenant_id

    class _DummySession:
        async def execute(self, *_, **__):
            class _Res:
                def scalars(self):
                    return self

                def first(self):
                    return None

            return _Res()

    async def _mock_session():
        return _DummySession()

    async def _tenant():
        return "t_test"

    app.dependency_overrides[get_session] = _mock_session
    app.dependency_overrides[require_tenant_id] = _tenant

    @app.get("/feature", dependencies=[Depends(require_quota("tokens", window="day", soft=False))])
    async def feature():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        res = await ac.get("/feature")
        assert res.status_code == 200
        assert res.json() == {"ok": True}
