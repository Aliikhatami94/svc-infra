from __future__ import annotations

import pytest

IDEMP = {"Idempotency-Key": "idem-usage-1"}


@pytest.mark.asyncio
async def test_post_usage_accepts_and_returns_id(client):
    body = {
        "metric": "tokens",
        "amount": 5,
        "idempotency_key": "k1",
        "metadata": {"m": 1},
    }
    res = await client.post("/_billing/usage", json=body, headers=IDEMP)
    assert res.status_code == 202
    data = res.json()
    assert data["id"] == "evt_test_1"
    assert data["accepted"] is True


@pytest.mark.asyncio
async def test_get_usage_lists_empty(client):
    res = await client.get("/_billing/usage", params={"metric": "tokens"})
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["next_cursor"] is None
