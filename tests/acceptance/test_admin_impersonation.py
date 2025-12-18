from __future__ import annotations

import pytest
from starlette.testclient import TestClient

pytestmark = [pytest.mark.acceptance, pytest.mark.admin, pytest.mark.security]


@pytest.fixture()
def local_client(_acceptance_app_ready):
    with TestClient(_acceptance_app_ready) as c:
        yield c


class TestAdminImpersonation:
    def test_start_forbidden_without_admin(self, local_client: TestClient):
        r = local_client.post("/admin/impersonate/start", json={"user_id": "u-2", "reason": "t"})
        assert r.status_code == 403

    def test_start_and_effect_with_admin(self, local_client: TestClient):
        # Temporarily grant admin role
        from svc_infra.api.fastapi.auth.security import _current_principal
        from tests.acceptance.app import _accept_principal
        from tests.acceptance.app import app as acceptance_app

        def _admin_principal():
            p = _accept_principal()
            p.user.roles = ["admin"]
            return p

        acceptance_app.dependency_overrides[_current_principal] = _admin_principal
        try:
            target = "u-imp"
            r = local_client.post(
                "/admin/impersonate/start", json={"user_id": target, "reason": "test"}
            )
            assert r.status_code == 204
            # Cookie should be set; subsequent request should reflect impersonated identity
            ok = local_client.get(f"/secure/owned/{target}")
            assert ok.status_code == 200
            no = local_client.get("/secure/owned/not-imp")
            assert no.status_code == 403
        finally:
            acceptance_app.dependency_overrides[_current_principal] = _accept_principal
