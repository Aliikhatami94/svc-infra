import asyncio

import httpx
import pytest
from fastapi import FastAPI  # type: ignore
from fastapi.routing import APIRouter  # type: ignore
from httpx import ASGITransport
from starlette.testclient import TestClient  # type: ignore

from svc_infra.api.fastapi.middleware.timeout import BodyReadTimeoutMiddleware

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


def test_handler_timeout_returns_504_problem():
    # Build a minimal app with a very small handler timeout
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
    from svc_infra.api.fastapi.middleware.timeout import HandlerTimeoutMiddleware

    app = FastAPI()
    app.add_middleware(HandlerTimeoutMiddleware, timeout_seconds=0.01)
    register_error_handlers(app)

    @app.get("/slow")
    async def _slow():
        await asyncio.sleep(0.2)
        return {"ok": True}

    with TestClient(app) as client:
        r = client.get("/slow")
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
