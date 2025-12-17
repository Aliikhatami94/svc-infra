"""
Tests for FastAPI setup and supporting helpers.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.ease import (
    EasyAppOptions,
    LoggingOptions,
    ObservabilityOptions,
    easy_service_api,
    easy_service_app,
)
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


def test_easy_app_options_from_env(monkeypatch):
    monkeypatch.setenv("ENABLE_LOGGING", "false")
    monkeypatch.setenv("ENABLE_OBS", "true")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LOG_FORMAT", "plain")
    monkeypatch.setenv("METRICS_PATH", "/metrics")
    monkeypatch.setenv("OBS_SKIP_PATHS", "/metrics, /health")

    opts = EasyAppOptions.from_env()

    assert opts.logging.enable is False
    assert opts.logging.level == "WARNING"
    assert opts.logging.fmt == "plain"
    assert opts.observability.enable is True
    assert opts.observability.metrics_path == "/metrics"
    assert list(opts.observability.skip_metric_paths) == ["/metrics", "/health"]


def test_easy_app_options_merge_prefers_overrides():
    base = EasyAppOptions(
        logging=LoggingOptions(enable=True, level="INFO", fmt="json"),
        observability=ObservabilityOptions(enable=True, metrics_path="/metrics"),
    )
    override = EasyAppOptions(
        logging=LoggingOptions(enable=False, level="DEBUG", fmt=None),
        observability=ObservabilityOptions(
            enable=False, skip_metric_paths=["/metrics"]
        ),
    )

    merged = base.merged_with(override)

    assert merged.logging.enable is False
    # Override supplies DEBUG even though fmt is None (falls back to base JSON)
    assert merged.logging.level == "DEBUG"
    assert merged.logging.fmt == "json"
    assert merged.observability.enable is False
    # skip_metric_paths overrides entirely
    assert list(merged.observability.skip_metric_paths) == ["/metrics"]


def test_easy_service_app_respects_logging_and_observability_flags(monkeypatch, mocker):
    monkeypatch.setenv("ENABLE_LOGGING", "true")
    monkeypatch.setenv("ENABLE_OBS", "true")
    setup_logging = mocker.patch("svc_infra.api.fastapi.ease.setup_logging")
    add_obs = mocker.patch("svc_infra.api.fastapi.ease.add_observability")

    easy_service_app(
        name="Svc", release="1.0.0", enable_logging=False, enable_observability=False
    )

    setup_logging.assert_not_called()
    add_obs.assert_not_called()


def test_easy_service_app_applies_options(monkeypatch, mocker):
    monkeypatch.delenv("METRICS_PATH", raising=False)
    monkeypatch.delenv("OBS_SKIP_PATHS", raising=False)
    setup_logging = mocker.patch("svc_infra.api.fastapi.ease.setup_logging")
    add_obs = mocker.patch("svc_infra.api.fastapi.ease.add_observability")

    options = EasyAppOptions(
        logging=LoggingOptions(enable=True, level="WARNING", fmt="plain"),
        observability=ObservabilityOptions(
            enable=True,
            metrics_path="/custom-metrics",
            skip_metric_paths=["/healthz"],
            db_engines=[object()],
        ),
    )

    easy_service_app(name="Svc", release="2.0.0", options=options)

    setup_logging.assert_called_once()
    kwargs = setup_logging.call_args.kwargs
    assert kwargs["level"] == "WARNING"
    assert kwargs["fmt"] == "plain"

    add_obs.assert_called_once()
    obs_args, obs_kwargs = add_obs.call_args
    assert obs_args[0].title == "Svc"
    assert obs_kwargs["metrics_path"] == "/custom-metrics"
    assert list(obs_kwargs["skip_metric_paths"]) == ["/healthz"]


def test_setup_service_api_infers_root_include_api_key(mocker):
    registrations = []

    def fake_register(app, base_package, prefix, environment):
        registrations.append((base_package, prefix))

    def fake_render_index_html(*args, **kwargs):
        return "<html></html>"

    records = []

    def fake_setup_mutators(*, service, spec, include_api_key, server_url):
        records.append((spec.tag if spec else None, include_api_key, server_url))
        return ()

    mocker.patch(
        "svc_infra.api.fastapi.setup.register_all_routers", side_effect=fake_register
    )
    mocker.patch(
        "svc_infra.api.fastapi.setup.render_index_html",
        side_effect=fake_render_index_html,
    )
    mocker.patch("svc_infra.api.fastapi.setup.apply_mutators")
    mocker.patch(
        "svc_infra.api.fastapi.setup.setup_mutators", side_effect=fake_setup_mutators
    )

    service = ServiceInfo(name="Svc", release="1.0")
    specs = [
        APIVersionSpec(
            tag="v1", routers_package="svc_infra.sample", include_api_key=True
        )
    ]

    app = setup_service_api(service=service, versions=specs)

    # First registration is for svc_infra defaults, second for the version, etc.
    assert any(pkg == "svc_infra.api.fastapi.routers" for pkg, _ in registrations)
    assert app.routes  # ensures mount happened

    # records[0] is parent spec None; expect include_api_key inferred True
    assert records[0] == (None, True, "/")
    # records[1] is child spec v1 with include flag True and server URL includes mount path
    assert records[1] == ("v1", True, "/v1")


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
    mocker.patch(
        "svc_infra.api.fastapi.setup.render_index_html", return_value="<html></html>"
    )
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
    mocker.patch(
        "svc_infra.api.fastapi.setup.render_index_html", return_value="<html></html>"
    )

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
