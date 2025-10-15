from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import FastAPI
from starlette.testclient import TestClient

import svc_infra.obs.metrics as metrics
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware
from svc_infra.api.fastapi.middleware.request_size_limit import RequestSizeLimitMiddleware


def test_emit_rate_limited_hook_called(monkeypatch):
    app = FastAPI()
    app.add_middleware(SimpleRateLimitMiddleware, limit=1, window=5, key_fn=lambda r: "k")

    @app.get("/ping")
    def ping():
        return {"ok": True}

    captured: List[Tuple[str, int, int]] = []

    def capture(key: str, limit: int, retry_after: int) -> None:
        captured.append((key, limit, retry_after))

    monkeypatch.setattr(metrics, "on_rate_limit_exceeded", capture, raising=False)

    c = TestClient(app)
    assert c.get("/ping").status_code == 200
    r = c.get("/ping")
    assert r.status_code == 429

    # Hook should have been called once with our key and limit
    assert captured, "expected on_rate_limit_exceeded to be called"
    k, lim, retry = captured[-1]
    assert k == "k"
    assert lim == 1
    assert isinstance(retry, int) and retry >= 0


def test_emit_suspect_payload_hook_called(monkeypatch):
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=10)

    @app.post("/echo")
    def echo(body: dict):
        return body

    captured2: List[Tuple[Optional[str], int]] = []

    def capture2(path: Optional[str], size: int) -> None:
        captured2.append((path, size))

    monkeypatch.setattr(metrics, "on_suspect_payload", capture2, raising=False)

    c = TestClient(app)
    # small request
    assert c.post("/echo", json={"x": "y"}).status_code == 200
    # large request to trigger 413 and hook
    r2 = c.post("/echo", json={"big": "x" * 100})
    assert r2.status_code == 413
    assert captured2, "expected on_suspect_payload to be called"
    path, size = captured2[-1]
    assert path == "/echo"
    assert isinstance(size, int) and size > 10
