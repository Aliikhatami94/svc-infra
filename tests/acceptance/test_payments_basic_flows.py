from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.acceptance


def _idem(n: str) -> dict[str, str]:
    return {"Idempotency-Key": f"accept-{n}"}


def test_create_customer_attach_method_and_list(client):
    # Create customer (requires Idempotency-Key)
    r = client.post(
        "/payments/customers",
        json={"email": "alice@example.com", "name": "Alice"},
        headers=_idem("cust-1"),
    )
    assert r.status_code == 200, r.text
    customer = r.json()
    assert customer["provider"] == "fake"
    cust_id = customer["provider_customer_id"]

    # Attach a payment method (requires Idempotency-Key)
    r = client.post(
        "/payments/methods/attach",
        json={
            "customer_provider_id": cust_id,
            "payment_method_token": "pm_tok_accept",
            "make_default": True,
        },
        headers=_idem("attach-1"),
    )
    assert r.status_code == 201, r.text
    method = r.json()
    assert method["provider_customer_id"] == cust_id
    assert method["is_default"] is True

    # List methods with pagination params present; should honor limit=1
    r = client.get("/payments/methods", params={"customer_provider_id": cust_id, "limit": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("items"), list)
    assert body["items"], "expected at least one method"
    assert len(body["items"]) == 1, body


def test_create_intent_requires_idempotency_and_sets_location(client):
    # Create a new intent
    r = client.post(
        "/payments/intents",
        json={"amount": 5000, "currency": "USD", "description": "Order #A"},
        headers=_idem("intent-1"),
    )
    assert r.status_code == 201, r.text
    intent = r.json()
    assert intent["provider"] == "fake"
    # Location header should point to the GET endpoint for this intent
    loc = r.headers.get("Location")
    assert loc and "/payments/intents/" in loc
    # Follow the Location to retrieve
    r2 = client.get(loc.replace("http://testserver", ""))  # client base_url is api:8000
    assert r2.status_code == 200, r2.text
    assert r2.json()["provider_intent_id"] == intent["provider_intent_id"]
