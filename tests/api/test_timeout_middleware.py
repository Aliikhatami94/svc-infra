import asyncio

import httpx
import pytest
from fastapi import FastAPI  # type: ignore
from fastapi.routing import APIRouter  # type: ignore
from httpx import ASGITransport
from starlette.testclient import TestClient  # type: ignore

from svc_infra.api.fastapi.middleware.timeout import BodyReadTimeoutMiddleware
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.setup import setup_service_api

fastapi = pytest.importorskip("fastapi")
router = APIRouter()


@router.get("/slow")
async def slow_handler():
    # Sleep longer than the non-prod default of 15 seconds? keep short by overriding via env
    await asyncio.sleep(0.2)
    return {"ok": True}


@router.post("/echo")
async def echo(payload: dict):
    return {"ok": True, "payload": payload}


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


@pytest.mark.asyncio
async def test_body_read_timeout_returns_408_problem():
    # Build a minimal app with a very small body read timeout
    app = FastAPI()
    app.add_middleware(BodyReadTimeoutMiddleware, timeout_seconds=0.05)

    @app.post("/echo")
    async def _accept(payload: dict):  # noqa: ANN001
        return {"ok": True, "payload": payload}

    # Create an async client backed by ASGITransport so we can stream request body slowly
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def gen():
            # Send first bytes, then pause longer than timeout
            yield b'{"a":'
            await asyncio.sleep(0.2)
            yield b"1}"

        r = await client.post("/echo", content=gen(), headers={"content-type": "application/json"})
        assert r.status_code == 408
        body = r.json()
        assert body.get("title") == "Request Timeout"
        assert body.get("status") == 408
        assert body.get("type") == "about:blank"
