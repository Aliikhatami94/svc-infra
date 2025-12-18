from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware


@pytest.fixture
def app():
    app = FastAPI()
    app.add_middleware(SimpleRateLimitMiddleware, limit=3, window=1, key_fn=lambda r: "k")

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_rate_limit_block_and_headers(app: FastAPI):
    c = TestClient(app)
    # First 3 pass
    for i in range(3):
        r = c.get("/ping")
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Limit") == "3"
        assert r.headers.get("X-RateLimit-Remaining") in {"2", "1", "0"}
        assert r.headers.get("X-RateLimit-Reset")

    # 4th is blocked
    r4 = c.get("/ping")
    assert r4.status_code == 429
    assert r4.headers.get("Retry-After") is not None

    # Wait for window reset
    time.sleep(1.1)
    r5 = c.get("/ping")
    assert r5.status_code == 200
