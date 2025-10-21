import time

import pytest


@pytest.mark.acceptance
def test_a204_handler_timeout_returns_504_problem(client):
    r = client.get("/_accept/timeouts/slow-handler", headers={"X-Request-Id": "a2-04"})
    assert r.status_code == 504
    data = r.json()
    assert data.get("title") == "Gateway Timeout"
    assert data.get("status") == 504
    assert data.get("type") == "about:blank"
    # traceId may or may not be present depending on handler implementation
    # If provided, it should be non-empty
    if "traceId" in data:
        assert data["traceId"].strip() != ""


@pytest.mark.acceptance
def test_a205_body_read_timeout_returns_408_problem(client):
    def gen():
        yield b'{"a":'
        time.sleep(0.2)
        yield b"1}"

    r = client.post(
        "/_accept/timeouts/slow-body",
        content=gen(),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 408
    data = r.json()
    assert data.get("title") == "Request Timeout"
    assert data.get("status") == 408
    assert data.get("type") == "about:blank"


@pytest.mark.acceptance
def test_a206_outbound_httpx_timeout_maps_to_504_problem(client):
    r = client.get("/_accept/timeouts/outbound-timeout")
    assert r.status_code == 504
    data = r.json()
    assert data.get("title") == "Gateway Timeout"
    assert data.get("status") == 504
    assert data.get("type") == "about:blank"
