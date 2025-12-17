from __future__ import annotations

import pytest

pytestmark = pytest.mark.acceptance


def test_billing_usage_ingest_returns_202(client):
    # Minimal smoke: billing router mounted, requires Idempotency-Key
    payload = {
        "metric": "tokens",
        "amount": 3,
        "idempotency_key": "acc-k1",
    }
    r = client.post(
        "/_billing/usage", json=payload, headers={"Idempotency-Key": "acc-k1"}
    )
    assert r.status_code == 202
    body = r.json()
    assert body.get("accepted") is True
    assert isinstance(body.get("id"), str)


def test_billing_list_aggregates_is_well_formed(client):
    # Our acceptance app uses a stub session, so expect empty list
    r = client.get("/_billing/usage", params={"metric": "tokens"})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
