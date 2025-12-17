from __future__ import annotations

import types

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.admin import add_admin
from svc_infra.api.fastapi.auth.security import Principal, _current_principal
from svc_infra.api.fastapi.db.sql.session import get_session

pytestmark = [pytest.mark.admin, pytest.mark.security]


def _make_app(with_admin: bool) -> FastAPI:
    app = FastAPI()

    # Make a simple principal; toggle admin role
    def _principal():
        user = types.SimpleNamespace(
            id="u-actor", roles=["admin"] if with_admin else ["user"]
        )
        return Principal(user=user, scopes=[], via="jwt")

    # Impersonation user loader just echoes back an object with id
    def _user_getter(_request, user_id: str):
        return types.SimpleNamespace(id=user_id)

    add_admin(app, impersonation_user_getter=_user_getter)
    app.dependency_overrides[_current_principal] = _principal

    # Override DB session dependency to avoid requiring SQL setup
    async def _fake_session():
        yield types.SimpleNamespace()

    app.dependency_overrides[get_session] = _fake_session
    return app


def test_start_requires_permission_and_logs(caplog):
    # Without admin → forbidden
    app = _make_app(with_admin=False)
    with TestClient(app) as c:
        r = c.post(
            "/admin/impersonate/start", json={"user_id": "u-imp", "reason": "unit"}
        )
        assert r.status_code == 403

    # With admin → 204 and log emitted
    app = _make_app(with_admin=True)
    with TestClient(app) as c:
        caplog.clear()
        with caplog.at_level("INFO"):
            r = c.post(
                "/admin/impersonate/start", json={"user_id": "u-imp", "reason": "unit"}
            )
        assert r.status_code == 204
        # Assert a start event was logged
        assert any(
            "admin.impersonation.started" in rec.getMessage() for rec in caplog.records
        )


def test_stop_logs(caplog):
    app = _make_app(with_admin=True)
    with TestClient(app) as c:
        # Start first to set cookie
        r = c.post(
            "/admin/impersonate/start", json={"user_id": "u-imp", "reason": "unit"}
        )
        assert r.status_code == 204
        caplog.clear()
        with caplog.at_level("INFO"):
            r = c.post("/admin/impersonate/stop")
        assert r.status_code == 204
        assert any(
            "admin.impersonation.stopped" in rec.getMessage() for rec in caplog.records
        )
