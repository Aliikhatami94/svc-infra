from __future__ import annotations

import os

import pytest


@pytest.mark.acceptance
@pytest.mark.ops
def test_a801_probes_basic(client):
    r1 = client.get("/_ops/live")
    r2 = client.get("/_ops/ready")
    r3 = client.get("/_ops/startup")
    assert r1.status_code == 200 and r1.json()["status"] == "ok"
    assert r2.status_code == 200 and r2.json()["status"] == "ok"
    assert r3.status_code == 200 and r3.json()["status"] == "ok"


@pytest.mark.acceptance
@pytest.mark.ops
def test_a802_maintenance_mode_blocks_non_get(client):
    # Ensure off initially
    os.environ["MAINTENANCE_MODE"] = "false"
    r_ok = client.post("/_ops/echo", json={"x": 1})
    assert r_ok.status_code == 200 and r_ok.json()["echo"]["x"] == 1

    # Turn on maintenance and verify non-GET returns 503
    client.post("/_ops/maintenance/set", json={"on": True})
    r_block = client.post("/_ops/echo", json={"x": 2})
    assert r_block.status_code == 503
    assert r_block.json().get("detail") == "maintenance"

    # GET should still work under maintenance
    r_get = client.get("/_ops/live")
    assert r_get.status_code == 200

    # Turn off
    client.post("/_ops/maintenance/set", json={"on": False})
    r_ok2 = client.post("/_ops/echo", json={"x": 3})
    assert r_ok2.status_code == 200 and r_ok2.json()["echo"]["x"] == 3


@pytest.mark.acceptance
@pytest.mark.ops
def test_a803_circuit_breaker_dependency(client):
    # Ensure circuit closed
    client.post("/_ops/circuit/set", json={"open": False})
    r_closed = client.get("/_ops/cb-check")
    assert r_closed.status_code == 200

    # Open circuit and assert 503
    client.post("/_ops/circuit/set", json={"open": True})
    r_open = client.get("/_ops/cb-check")
    assert r_open.status_code == 503
    assert r_open.json().get("detail") == "circuit open"

    # Close again
    client.post("/_ops/circuit/set", json={"open": False})
    r_closed2 = client.get("/_ops/cb-check")
    assert r_closed2.status_code == 200
