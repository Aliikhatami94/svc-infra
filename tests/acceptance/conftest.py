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
    def __init__(self, app, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.new_event_loop()
        self._owns_loop = loop is None  # Track if we created the loop
        self._transport = httpx.ASGITransport(app=app)
        self._client = httpx.AsyncClient(
            transport=self._transport,
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
        # Also close the transport to release any resources
        if hasattr(self._transport, "aclose"):
            self._run(self._transport.aclose())
        # Don't close the loop here - let the fixture manage the loop lifecycle


# Module-level cache for shared app lifecycle between client and _acceptance_app_ready fixtures
_shared_app_state: dict = {}


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
        # Mark the app as started for _acceptance_app_ready fixture
        _shared_app_state["started"] = True
        _shared_app_state["loop"] = loop
        client = _SyncASGIClient(acceptance_app, loop=loop)  # Pass the loop
        try:
            yield client
        finally:
            client.close()
            loop.run_until_complete(acceptance_app.router.shutdown())
            _shared_app_state["started"] = False
            # Cancel any remaining tasks to prevent hanging
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                # Use wait_for with timeout to prevent infinite hang
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=2.0,
                        )
                    )
                except asyncio.TimeoutError:
                    pass  # Tasks didn't complete in time, force close
            # Stop the loop to clear any lingering callbacks
            loop.stop()
    finally:
        if not loop.is_closed():
            loop.close()
        asyncio.set_event_loop(prev_loop)


@pytest.fixture(autouse=True)
def _reset_tenancy_between_tests(request):
    """Reset in-memory tenancy state before each tenancy-marked test.

    Applies to both in-process and external (BASE_URL) modes to prevent state leakage
    across tests when a shared server process persists.
    """
    # Only for tests marked 'tenancy'
    if request.node.get_closest_marker("tenancy") is None:
        return
    # Lazily get client only when we actually need it (for tenancy tests)
    client = request.getfixturevalue("client")
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

    NOTE: This fixture shares the app lifecycle with the `client` fixture
    to avoid double startup/shutdown issues.
    """
    # Skip if using external BASE_URL
    if os.getenv("BASE_URL"):
        pytest.skip("_acceptance_app_ready not available when using BASE_URL")
        return

    from .app import app as acceptance_app  # lazy import

    # Check if app is already started by the client fixture
    if _shared_app_state.get("started"):
        yield acceptance_app
        return

    try:
        prev_loop = asyncio.get_running_loop()
    except RuntimeError:
        prev_loop = None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(acceptance_app.router.startup())
        _shared_app_state["started"] = True
        _shared_app_state["loop"] = loop
        yield acceptance_app
        loop.run_until_complete(acceptance_app.router.shutdown())
        _shared_app_state["started"] = False
        # Cancel any remaining tasks to prevent hanging
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            # Use wait_for with timeout to prevent infinite hang
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True), timeout=2.0
                    )
                )
            except asyncio.TimeoutError:
                pass  # Tasks didn't complete in time, force close
        # Stop the loop to clear any lingering callbacks
        loop.stop()
    finally:
        if not loop.is_closed():
            loop.close()
        asyncio.set_event_loop(prev_loop)
