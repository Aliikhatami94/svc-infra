from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Generator

import httpx
import pytest

from .app import app as acceptance_app

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def _acceptance_app_ready():
    """Ensure FastAPI startup/shutdown handlers run for the in-process app."""

    try:
        prev_loop = asyncio.get_running_loop()
    except RuntimeError:
        prev_loop = None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(acceptance_app.router.startup())
        yield acceptance_app
    finally:
        loop.run_until_complete(acceptance_app.router.shutdown())
        loop.close()
        asyncio.set_event_loop(prev_loop)


class _SyncASGIClient:
    def __init__(self, app) -> None:
        self._loop = asyncio.new_event_loop()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            timeout=10.0,
        )

    def _run(self, coro):
        try:
            asyncio.set_event_loop(self._loop)
        except RuntimeError:
            pass
        return self._loop.run_until_complete(coro)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self._run(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    def close(self) -> None:
        self._run(self._client.aclose())
        self._loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(scope="session")
def client(_acceptance_app_ready) -> Generator[httpx.Client, None, None]:
    """HTTPX client for acceptance scenarios.

    If ``BASE_URL`` is provided we target that network endpoint so the
    harness can exercise a real stack (for example the docker-compose
    setup described in ``docs/acceptance.md``).  When the environment
    variable is not present we fall back to running the acceptance app
    in-process via ``ASGITransport`` so the tests remain fully
    self-contained.
    """

    base_url = os.getenv("BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=10.0) as c:
            yield c
    else:
        client = _SyncASGIClient(_acceptance_app_ready)
        try:
            yield client
        finally:
            client.close()
