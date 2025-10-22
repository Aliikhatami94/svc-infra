from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient


def test_add_cache_wires_startup_shutdown_and_state(monkeypatch):
    app = FastAPI()

    # Patch backend functions to observe calls without touching real backend
    with patch("svc_infra.cache.add._setup_cache") as setup_mock, patch(
        "svc_infra.cache.add._wait_ready", new_callable=AsyncMock
    ) as ready_mock, patch(
        "svc_infra.cache.add._shutdown_cache", new_callable=AsyncMock
    ) as shutdown_mock, patch(
        "svc_infra.cache.add._instance"
    ) as instance_mock:
        instance_mock.return_value = object()

        # Import and wire
        from svc_infra.cache import add_cache

        # Call twice to ensure idempotence (handlers should register once)
        add_cache(app)
        add_cache(app)

        # Trigger lifecycle via TestClient
        with TestClient(app) as _client:
            pass

        # setup called once at startup
        assert setup_mock.call_count == 1
        # readiness awaited once
        assert ready_mock.await_count == 1
        # shutdown awaited once
        assert shutdown_mock.await_count == 1
        # state exposed
        assert hasattr(app.state, "cache")
        assert app.state.cache is instance_mock.return_value


def test_add_cache_no_app_initializes_without_crash():
    # Patch setup to ensure it is invoked with defaults
    with patch("svc_infra.cache.add._setup_cache") as setup_mock:
        from svc_infra.cache import add_cache

        shutdown = add_cache(None)
        assert callable(shutdown)
        assert setup_mock.call_count == 1
