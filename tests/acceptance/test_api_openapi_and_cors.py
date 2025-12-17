from __future__ import annotations

import httpx
import pytest


@pytest.mark.acceptance
def test_openapi_present(client: httpx.Client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    # Basic invariants
    assert "openapi" in data
    assert "paths" in data and "/ping" in data["paths"]


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("https://example.com", True),
        (
            "http://not-allowed.local",
            True,
        ),  # acceptance app sets public_cors_origins=["*"]
    ],
)
def test_cors_preflight_options(client: httpx.Client, origin: str, allowed: bool):
    # Preflight request against known route
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
    }
    r = client.options("/ping", headers=headers)
    assert r.status_code in (200, 204)
    acao = r.headers.get("access-control-allow-origin")
    if allowed:
        assert acao in ("*", origin)
    else:
        assert acao is None
