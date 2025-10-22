import os

import httpx
import pytest

from svc_infra.http import get_default_timeout_seconds, new_async_httpx_client, new_httpx_client


@pytest.mark.parametrize("val", ["0.123", "2.5", "10"])  # string env values
def test_sync_client_uses_env_timeout(monkeypatch, val):
    monkeypatch.setenv("HTTP_CLIENT_TIMEOUT_SECONDS", val)
    client = new_httpx_client()
    try:
        assert isinstance(client.timeout, httpx.Timeout)
        expected = float(val)
        # httpx.Timeout exposes attributes connect/read/write/pool
        assert client.timeout.connect == pytest.approx(expected)
        assert client.timeout.read == pytest.approx(expected)
        assert client.timeout.write == pytest.approx(expected)
        assert client.timeout.pool == pytest.approx(expected)
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_client_uses_env_timeout(monkeypatch):
    monkeypatch.setenv("HTTP_CLIENT_TIMEOUT_SECONDS", "0.321")
    async with new_async_httpx_client() as client:
        assert isinstance(client.timeout, httpx.Timeout)
        expected = 0.321
        assert client.timeout.connect == pytest.approx(expected)
        assert client.timeout.read == pytest.approx(expected)
        assert client.timeout.write == pytest.approx(expected)
        assert client.timeout.pool == pytest.approx(expected)


def test_default_timeout_pick(monkeypatch):
    # When env unset, returns a sane default (10.0)
    monkeypatch.delenv("HTTP_CLIENT_TIMEOUT_SECONDS", raising=False)
    val = get_default_timeout_seconds()
    assert isinstance(val, float)
    assert val == pytest.approx(10.0)
