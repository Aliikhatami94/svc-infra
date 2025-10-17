from __future__ import annotations

import os
from contextlib import contextmanager

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.ops.add import (
    add_maintenance_mode,
    add_probes,
    circuit_breaker_dependency,
)


@contextmanager
def envset(key: str, value: str):
    old = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old is None:
            del os.environ[key]
        else:
            os.environ[key] = old


def test_probes_and_maintenance_mode():
    app = FastAPI()
    add_probes(app)
    add_maintenance_mode(app)

    with TestClient(app) as client:
        # Probes
        assert client.get("/_ops/live").status_code == 200
        assert client.get("/_ops/ready").status_code == 200
        assert client.get("/_ops/startup").status_code == 200

        # Maintenance gate blocks non-GET when enabled
        with envset("MAINTENANCE_MODE", "true"):
            r = client.post("/noop")
            assert r.status_code == 503


def test_circuit_breaker_dependency():
    app = FastAPI()

    @app.get("/ok", dependencies=[Depends(circuit_breaker_dependency())])
    async def ok():  # noqa: D401, ANN201
        return {"ok": True}

    with TestClient(app) as client:
        # Normal
        assert client.get("/ok").status_code == 200
        # Breaker open
        with envset("CIRCUIT_OPEN", "true"):
            assert client.get("/ok").status_code == 503
