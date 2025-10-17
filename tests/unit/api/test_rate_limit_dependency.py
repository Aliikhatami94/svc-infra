from __future__ import annotations

from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter


def test_per_route_rate_limiter_blocks_on_exceed():
    app = FastAPI()
    limiter = rate_limiter(limit=2, window=1, key_fn=lambda r: "k")

    @app.get("/a", dependencies=[Depends(limiter)])
    def a():
        return {"ok": True}

    c = TestClient(app)
    assert c.get("/a").status_code == 200
    assert c.get("/a").status_code == 200
    r = c.get("/a")
    assert r.status_code == 429
    assert r.headers.get("Retry-After") is not None
