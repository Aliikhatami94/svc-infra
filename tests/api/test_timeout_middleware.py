import asyncio

import pytest
from fastapi import FastAPI  # type: ignore
from fastapi.routing import APIRouter  # type: ignore
from starlette.testclient import TestClient  # type: ignore

from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.setup import setup_service_api

fastapi = pytest.importorskip("fastapi")
router = APIRouter()


@router.get("/slow")
async def slow_handler():
    # Sleep longer than the non-prod default of 15 seconds? keep short by overriding via env
    await asyncio.sleep(0.2)
    return {"ok": True}


def _make_app(timeout_seconds: int) -> FastAPI:
    # Patch env for the test process
    import os

    os.environ["REQUEST_TIMEOUT_SECONDS"] = str(timeout_seconds)

    service = ServiceInfo(name="TimeoutTest", release="0.0.1")
    spec = APIVersionSpec(tag="v1", routers_package=None)
    app = setup_service_api(service=service, versions=[spec])
    # Register test route on mounted child app
    # Mounted under /v1
    child: FastAPI = app.apps.get("v1")  # type: ignore[attr-defined]
    child.include_router(router)
    return app


def test_handler_timeout_returns_504_problem():
    app = _make_app(timeout_seconds=0)  # force immediate timeout
    with TestClient(app) as client:
        r = client.get("/v1/slow")
        assert r.status_code == 504
        body = r.json()
        # Problem+JSON fields
        assert body.get("title") == "Gateway Timeout"
        assert body.get("status") == 504
        assert body.get("type") == "about:blank"
