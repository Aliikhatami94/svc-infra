from __future__ import annotations

import pytest
from starlette.testclient import TestClient

# Run these under acceptance and security markers
pytestmark = [pytest.mark.acceptance, pytest.mark.security]


@pytest.fixture()
def local_client(_acceptance_app_ready):
    """Client pinned to the in-process acceptance app.

    This bypasses BASE_URL so tests can exercise acceptance-only routes
    defined in tests/acceptance/app.py (not present in the docker API).
    """
    with TestClient(_acceptance_app_ready) as c:
        yield c


class TestSecurityAcceptance:
    def test_rbac_denied(self, local_client: TestClient):
        # Default principal has no roles → missing user.write permission
        r = local_client.get("/secure/admin-only")
        assert r.status_code == 403
        assert "missing_permissions" in r.json().get("detail", "")

    def test_rbac_allowed_with_admin_role(self, local_client: TestClient, monkeypatch):
        # Temporarily grant admin role via dependency override
        from tests.acceptance.app import _accept_principal
        from tests.acceptance.app import app as acceptance_app

        def _admin_principal():
            p = _accept_principal()
            p.user.roles = ["admin"]
            return p

        from svc_infra.api.fastapi.auth.security import _current_principal

        acceptance_app.dependency_overrides[_current_principal] = _admin_principal
        try:
            r = local_client.get("/secure/admin-only")
            assert r.status_code == 200
            assert r.json() == {"ok": True}
        finally:
            # restore baseline
            acceptance_app.dependency_overrides[_current_principal] = _accept_principal

    def test_abac_ownership(self, local_client: TestClient):
        # user.id is 'u-1' set by acceptance principal; ABAC should pass when owner_id matches
        r_ok = local_client.get("/secure/owned/u-1")
        assert r_ok.status_code == 200
        # different owner → forbidden
        r_no = local_client.get("/secure/owned/u-2")
        assert r_no.status_code == 403

    def test_sessions_list_requires_permission(self, local_client: TestClient):
        # No admin role → listing sessions should be forbidden (security.session.list)
        r = local_client.get("/users/sessions/me")
        assert r.status_code == 403
        assert "missing_permissions" in r.json().get("detail", "")

    def test_sessions_list_with_admin(self, local_client: TestClient):
        # Grant admin role to allow listing
        from svc_infra.api.fastapi.auth.security import _current_principal
        from tests.acceptance.app import _accept_principal
        from tests.acceptance.app import app as acceptance_app

        def _admin_principal():
            p = _accept_principal()
            p.user.roles = ["admin"]
            return p

        acceptance_app.dependency_overrides[_current_principal] = _admin_principal
        try:
            r = local_client.get("/users/sessions/me")
            assert r.status_code in (200, 204) or r.status_code == 200
            if r.status_code == 200:
                assert isinstance(r.json(), list)
        finally:
            acceptance_app.dependency_overrides[_current_principal] = _accept_principal
