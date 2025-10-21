from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Generator

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    def close(self) -> None:
        self._run(self._client.aclose())
        self._loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(scope="session")
def client() -> Generator[httpx.Client, None, None]:
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
        return

    # In-process fallback: lazily import acceptance app and run startup/shutdown
    from .app import app as acceptance_app  # lazy to avoid deps when BASE_URL is set

    try:
        prev_loop = asyncio.get_running_loop()
    except RuntimeError:
        prev_loop = None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(acceptance_app.router.startup())
        client = _SyncASGIClient(acceptance_app)
        try:
            yield client
        finally:
            client.close()
            loop.run_until_complete(acceptance_app.router.shutdown())
    finally:
        loop.close()
        asyncio.set_event_loop(prev_loop)


@pytest.fixture(autouse=True)
def _reset_tenancy_between_tests(request, client: httpx.Client):
    """Reset in-memory tenancy state before each tenancy-marked test.

    Applies to both in-process and external (BASE_URL) modes to prevent state leakage
    across tests when a shared server process persists.
    """
    # Only for tests marked 'tenancy'
    if request.node.get_closest_marker("tenancy") is None:
        return
    try:
        r = client.post("/tenancy/_reset")
        assert r.status_code in (200, 204)
    except Exception:
        # Best-effort; don't fail test collection if reset isn't available
        pass


@pytest.fixture(scope="session")
def _acceptance_app_ready():
    """Provide the acceptance FastAPI app with startup/shutdown executed.

    This is used by a subset of acceptance tests that still rely on
    Starlette's TestClient directly rather than the shared httpx client.
    """

    from .app import app as acceptance_app  # lazy import

    try:
        prev_loop = asyncio.get_running_loop()
    except RuntimeError:
        prev_loop = None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(acceptance_app.router.startup())
        yield acceptance_app
        loop.run_until_complete(acceptance_app.router.shutdown())
    finally:
        loop.close()
        asyncio.set_event_loop(prev_loop)
