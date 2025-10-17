"""
Tests for FastAPI setup and supporting helpers.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.ease import EasyAppOptions, easy_service_api, easy_service_app
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware
from svc_infra.api.fastapi.middleware.request_id import RequestIdMiddleware
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.setup import _setup_middlewares, setup_service_api


class TestEasyBuilders:
    """Smoke tests for the convenience builders."""

    def test_easy_service_app_defaults(self):
        app = easy_service_app(name="Test Service", release="1.0.0")

        assert isinstance(app, FastAPI)
        assert app.title == "Test Service"
        assert app.version == "1.0.0"

    def test_easy_service_app_with_options(self):
        options = EasyAppOptions()
        app = easy_service_app(name="Custom Service", release="2.0.0", options=options)

        assert app.title == "Custom Service"
        assert app.version == "2.0.0"

    def test_easy_service_api_defaults(self):
        app = easy_service_api(name="Service API", release="0.1.0")

        assert isinstance(app, FastAPI)
        assert app.title == "Service API"
        assert app.version == "0.1.0"

    def test_easy_service_api_overrides(self):
        app = easy_service_api(name="Custom API", release="3.0.0")

        assert app.title == "Custom API"
        assert app.version == "3.0.0"


def _build_service_app(
    *,
    mocker,
    versions: list[APIVersionSpec] | None = None,
    root_routers: list[str] | None = None,
    public_cors_origins: list[str] | str | None = None,
) -> FastAPI:
    """
    Helper to build a service app with router/HTML rendering patched out so tests
    focus on middleware and configuration.
    """
    mocker.patch("svc_infra.api.fastapi.setup.register_all_routers")
    mocker.patch("svc_infra.api.fastapi.setup.render_index_html", return_value="<html></html>")
    service = ServiceInfo(name="Payments", release="1.2.3")
    specs = versions or [APIVersionSpec(tag="v1")]
    return setup_service_api(
        service=service,
        versions=specs,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
    )


def test_setup_service_api_mounts_versions_and_calls_router_registration(mocker):
    register = mocker.patch("svc_infra.api.fastapi.setup.register_all_routers")
    mocker.patch("svc_infra.api.fastapi.setup.render_index_html", return_value="<html></html>")

    service = ServiceInfo(name="Payments", release="1.2.3")
    specs = [APIVersionSpec(tag="v1", routers_package="svc_infra.api.fastapi.payments")]
    app = setup_service_api(
        service=service,
        versions=specs,
        root_routers=["svc_infra.custom.root"],
    )

    mount_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/v1" in mount_paths
    # Expect: root routers once, custom root routers, and version router registration.
    assert register.call_count == 3


def test_setup_service_api_applies_cors_configuration(mocker):
    app = _build_service_app(
        mocker=mocker,
        public_cors_origins=["https://example.org", "https://api.example.org"],
    )

    cors_middleware = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors_middleware.kwargs["allow_origins"] == [
        "https://example.org",
        "https://api.example.org",
    ]
    assert cors_middleware.kwargs["allow_credentials"] is True


def test_setup_service_api_cors_strict_by_default(mocker, monkeypatch):
    # Ensure env not set -> no CORS middleware added
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    app = _build_service_app(mocker=mocker, public_cors_origins=None)
    assert all(m.cls is not CORSMiddleware for m in app.user_middleware)


def test_setup_service_api_cors_from_env(mocker, monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.example, https://b.example")
    app = _build_service_app(mocker=mocker, public_cors_origins=None)
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_origins"] == ["https://a.example", "https://b.example"]


def test_setup_service_api_sets_route_logger_header(mocker):
    app = _build_service_app(mocker=mocker)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Handled-By"].startswith("GET ")


def test_setup_middlewares_registers_expected_middlewares():
    app = FastAPI()
    _setup_middlewares(app)

    middleware_classes = {m.cls for m in app.user_middleware}
    assert RequestIdMiddleware in middleware_classes
    assert CatchAllExceptionMiddleware in middleware_classes
    assert IdempotencyMiddleware in middleware_classes
    assert SimpleRateLimitMiddleware in middleware_classes


def test_idempotency_middleware_replays_cached_response():
    app = FastAPI()
    _setup_middlewares(app)

    @app.post("/echo")
    async def echo(payload: dict[str, Any]):
        return {"echo": payload}

    client = TestClient(app)
    headers = {"Idempotency-Key": "cache-key-123"}

    first = client.post("/echo", json={"value": 1}, headers=headers)
    second = client.post("/echo", json={"value": 1}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
