from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.middleware.request_size_limit import RequestSizeLimitMiddleware


def test_request_size_limit_blocks_large_payload():
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=10)

    @app.post("/echo")
    def echo(body: dict):
        return body

    c = TestClient(app)
    # small request
    assert c.post("/echo", json={"x": "y"}).status_code == 200
    # large request
    r2 = c.post("/echo", json={"big": "x" * 100})
    assert r2.status_code == 413
