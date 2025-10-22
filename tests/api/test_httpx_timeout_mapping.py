import pytest

try:
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
except Exception:  # pragma: no cover - allow skip when FastAPI isn't available in this env
    FastAPI = None  # type: ignore


@pytest.mark.skipif(FastAPI is None, reason="FastAPI not available in test environment")
def test_httpx_timeout_maps_to_504_problem():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise httpx.Timeout("read timeout")

    client = TestClient(app)
    resp = client.get("/boom")
    assert resp.status_code == 504
    data = resp.json()
    assert data["title"] == "Gateway Timeout"
    assert data["status"] == 504
    assert data["type"] == "about:blank"
