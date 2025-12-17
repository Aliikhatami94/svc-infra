from __future__ import annotations

import pytest


@pytest.mark.acceptance
@pytest.mark.tenancy
class TestTenancyAcceptance:
    def test_a601_create_injects_tenant_and_list_scoped(self, client):
        # Default auth identity resolves to tenant "accept-tenant" via acceptance app override.
        r1 = client.post("/tenancy/widgets", json={"name": "alpha"})
        assert r1.status_code == 201
        body1 = r1.json()
        assert body1["tenant_id"] == "accept-tenant"

        # Switch to another tenant via X-Accept-Tenant header and create there
        r2 = client.post(
            "/tenancy/widgets",
            json={"name": "beta"},
            headers={"X-Accept-Tenant": "t-2"},
        )
        assert r2.status_code == 201
        body2 = r2.json()
        assert body2["tenant_id"] == "t-2"

        # List for default tenant returns only its items
        l1 = client.get("/tenancy/widgets")
        assert l1.status_code == 200
        ids1 = [it["id"] for it in l1.json()]
        assert body1["id"] in ids1
        assert body2["id"] not in ids1

        # List for tenant t-2 returns only its items
        l2 = client.get("/tenancy/widgets", headers={"X-Accept-Tenant": "t-2"})
        assert l2.status_code == 200
        ids2 = [it["id"] for it in l2.json()]
        assert body2["id"] in ids2
        assert body1["id"] not in ids2

    def test_a602_cross_tenant_404(self, client):
        # Create under tenant A
        r = client.post("/tenancy/widgets", json={"name": "solo"})
        assert r.status_code == 201
        wid = r.json()["id"]

        # Attempt to GET under another tenant should 404
        g = client.get(f"/tenancy/widgets/{wid}", headers={"X-Accept-Tenant": "other"})
        assert g.status_code == 404

    def test_a603_per_tenant_quota_enforced(self, client):
        # Quota default is 2 per tenant
        r1 = client.post("/tenancy/widgets", json={"name": "q1"})
        r2 = client.post("/tenancy/widgets", json={"name": "q2"})
        assert r1.status_code == 201
        assert r2.status_code == 201

        r3 = client.post("/tenancy/widgets", json={"name": "q3"})
        # Should exceed and return 429 with Retry-After
        assert r3.status_code == 429
        assert r3.headers.get("Retry-After") is not None
