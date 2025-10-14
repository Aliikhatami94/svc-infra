"""
Tests for observability setup utilities.
"""

from __future__ import annotations

from unittest.mock import Mock

from fastapi import FastAPI

from svc_infra.obs.add import add_observability


def create_settings(*, enabled: bool, path: str = "/metrics"):
    class _Settings:
        METRICS_ENABLED = enabled
        METRICS_PATH = path

    return _Settings()


def test_add_observability_registers_metrics(mocker):
    app = FastAPI()
    engine_one = Mock(name="engine_one")
    engine_two = Mock(name="engine_two")

    mocker.patch(
        "svc_infra.obs.add.ObservabilitySettings", return_value=create_settings(enabled=True)
    )
    add_prometheus = mocker.patch("svc_infra.obs.metrics.asgi.add_prometheus")
    bind_pool_metrics = mocker.patch(
        "svc_infra.obs.metrics.sqlalchemy.bind_sqlalchemy_pool_metrics"
    )
    instrument_requests = mocker.patch("svc_infra.obs.metrics.http.instrument_requests")
    instrument_httpx = mocker.patch("svc_infra.obs.metrics.http.instrument_httpx")

    shutdown = add_observability(
        app,
        db_engines=[engine_one, engine_two],
        metrics_path="/custom/metrics",
        skip_metric_paths=["/health", "/_internal"],
    )

    assert callable(shutdown)
    add_prometheus.assert_called_once_with(
        app,
        path="/custom/metrics",
        skip_paths=("/health", "/_internal"),
    )
    bind_pool_metrics.assert_any_call(engine_one)
    bind_pool_metrics.assert_any_call(engine_two)
    instrument_requests.assert_called_once()
    instrument_httpx.assert_called_once()


def test_add_observability_skips_when_disabled(mocker):
    app = FastAPI()

    mocker.patch(
        "svc_infra.obs.add.ObservabilitySettings", return_value=create_settings(enabled=False)
    )
    add_prometheus = mocker.patch("svc_infra.obs.metrics.asgi.add_prometheus")
    bind_pool_metrics = mocker.patch(
        "svc_infra.obs.metrics.sqlalchemy.bind_sqlalchemy_pool_metrics"
    )

    add_observability(app)

    add_prometheus.assert_not_called()
    bind_pool_metrics.assert_not_called()
