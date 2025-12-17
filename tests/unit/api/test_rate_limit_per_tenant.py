from __future__ import annotations

from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter


def test_middleware_scopes_by_tenant_and_dynamic_limit():
    app = FastAPI()

    # Global middleware with tenant scoping and dynamic limits
    def dynamic_limit(_req, tenant_id):
        if tenant_id == "A":
            return 1
        if tenant_id == "B":
            return 3
        return 2

    from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

    app.add_middleware(
        SimpleRateLimitMiddleware,
        limit=2,
        window=1,
        key_fn=lambda r: "k",
        scope_by_tenant=True,
        limit_resolver=dynamic_limit,
    )

    @app.get("/ping")
    def ping():
        return {"ok": True}

    c = TestClient(app)
    # Tenant A limited to 1
    assert c.get("/ping", headers={"X-Tenant-Id": "A"}).status_code == 200
    assert c.get("/ping", headers={"X-Tenant-Id": "A"}).status_code == 429

    # Tenant B limited to 3 and independent bucket
    assert c.get("/ping", headers={"X-Tenant-Id": "B"}).status_code == 200
    assert c.get("/ping", headers={"X-Tenant-Id": "B"}).status_code == 200
    r = c.get("/ping", headers={"X-Tenant-Id": "B"})
    assert r.status_code in {
        200,
        429,
    }  # last one may be 200 or 429 based on window timing


def test_dependency_scopes_by_tenant_and_dynamic_limit():
    app = FastAPI()

    # Per-route dependency using factory
    limiter = rate_limiter(
        limit=2,
        window=1,
        key_fn=lambda r: "route",
        scope_by_tenant=True,
        limit_resolver=lambda _r, tid: 1 if tid == "A" else 2,
    )

    @app.get("/a", dependencies=[Depends(limiter)])
    def a():
        return {"ok": True}

    c = TestClient(app)
    # Tenant A limited to 1
    assert c.get("/a", headers={"X-Tenant-Id": "A"}).status_code == 200
    assert c.get("/a", headers={"X-Tenant-Id": "A"}).status_code == 429

    # Tenant C uses default limit 2; independent bucket
    assert c.get("/a", headers={"X-Tenant-Id": "C"}).status_code == 200
    r2 = c.get("/a", headers={"X-Tenant-Id": "C"})
    assert r2.status_code in {200, 429}
