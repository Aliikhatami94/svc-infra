from __future__ import annotations

import os

import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from svc_infra.api.fastapi.ops.add import (
    add_maintenance_mode,
    add_probes,
    circuit_breaker_dependency,
)

pytestmark = pytest.mark.ops


def make_app():
    app = FastAPI()
    add_probes(app, prefix="/_ops", include_in_schema=False)

    @app.get("/guarded", dependencies=[Depends(circuit_breaker_dependency())])
    async def guarded():
        return {"ok": True}

    add_maintenance_mode(app)
    return app


def test_probes_respond_ok():
    app = make_app()
    with TestClient(app) as c:
        assert c.get("/_ops/live").status_code == 200
        assert c.get("/_ops/ready").status_code == 200
        assert c.get("/_ops/startup").status_code == 200


def test_breaker_trips_and_resets(monkeypatch):
    app = make_app()
    with TestClient(app) as c:
        # Closed by default
        r = c.get("/guarded")
        assert r.status_code == 200

        # Trip the breaker
        monkeypatch.setenv("CIRCUIT_OPEN", "1")
        r = c.get("/guarded")
        assert r.status_code == 503

        # Reset
        monkeypatch.delenv("CIRCUIT_OPEN", raising=False)
        r = c.get("/guarded")
        assert r.status_code == 200
