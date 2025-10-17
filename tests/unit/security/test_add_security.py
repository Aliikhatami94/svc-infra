from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from svc_infra.security.add import add_security


def _build_app():
    app = FastAPI()

    @app.get("/")
    def _root():
        return {"ok": True}

    return app


def test_add_security_applies_header_overrides():
    app = _build_app()

    add_security(
        app,
        cors_origins=["https://example.org"],
        headers_overrides={
            "Strict-Transport-Security": "max-age=60",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )

    client = TestClient(app)
    response = client.get("/", headers={"Origin": "https://example.org"})

    assert response.status_code == 200
    # Security headers should include overrides
    assert response.headers["Strict-Transport-Security"] == "max-age=60"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    # CORS should reflect the allowed origin
    assert response.headers["access-control-allow-origin"] == "https://example.org"


def test_add_security_reads_cors_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.example, https://b.example")

    app = _build_app()
    add_security(app)

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_origins"] == ["https://a.example", "https://b.example"]


def test_add_security_can_disable_hsts_preload(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    app = _build_app()

    add_security(app, enable_hsts_preload=False)

    client = TestClient(app)
    response = client.get("/")

    assert "preload" not in response.headers["Strict-Transport-Security"].lower()


def test_add_security_can_install_session_middleware(monkeypatch):
    app = _build_app()

    add_security(app, install_session_middleware=True, session_secret_key="secret")

    session_middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "SessionMiddleware"
    )
    assert session_middleware.kwargs["session_cookie"] == "svc_session"
    assert session_middleware.kwargs["max_age"] == 4 * 3600
    assert session_middleware.kwargs["same_site"] == "lax"
    assert session_middleware.kwargs["https_only"] is False
