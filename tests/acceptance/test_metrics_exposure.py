from __future__ import annotations

import os

import pytest


@pytest.mark.ops
def test_metrics_endpoint_exposes_basic_series(client):
    # Ensure observability is enabled in acceptance env
    os.environ.setdefault("ENABLE_OBS", "true")
    os.environ.setdefault("METRICS_PATH", "/metrics")

    r = client.get("/metrics")
    # If prometheus-client is missing the handler returns 501; treat as skip
    if r.status_code == 501:
        pytest.skip("prometheus-client not installed for acceptance run")

    assert r.status_code == 200
    body = r.text
    # Core HTTP metrics
    assert "http_server_requests_total" in body
    assert "http_server_request_duration_seconds" in body
    assert "http_server_inflight_requests" in body
    # DB pool metrics should appear when a SQLAlchemy engine is present
    assert "db_pool_in_use" in body
    assert "db_pool_available" in body
