from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.acceptance


BASE_TOPIC = "accept.topic"
RECEIVER_URL = "http://testserver/_accept/webhooks/receiver"


def _subscribe(client, *, secret: str):
    r = client.post(
        "/_webhooks/subscriptions",
        json={"topic": BASE_TOPIC, "url": RECEIVER_URL, "secret": secret},
    )
    assert r.status_code == 200


def _test_fire(client, payload: dict):
    r = client.post(
        "/_webhooks/test-fire",
        json={"topic": BASE_TOPIC, "payload": payload},
    )
    assert r.status_code == 200
    return r.json()["outbox_id"]


def _process_one(client) -> bool:
    r = client.post("/jobs/process-one")
    assert r.status_code == 200
    return bool(r.json()["processed"])


def test_a501_signature_and_delivery_with_retry(client):
    # Configure receiver secrets and make it fail once
    secret = "supersecret"
    client.post("/_accept/webhooks/config", json={"secrets": [secret], "fail_first": 1})
    _subscribe(client, secret=secret)

    # Fire a test event
    event = {"hello": "world", "version": 1}
    outbox_id = _test_fire(client, event)

    # First tick schedules the outbox job, then processing should fail (receiver 500)
    client.post("/scheduler/tick")
    assert _process_one(client) is True

    # Immediate second process should find nothing due to backoff
    assert _process_one(client) is False

    # Force the job to be due again (acceptance helper) and process → should succeed now
    client.post("/jobs/make-due", json={})
    assert _process_one(client) is True

    # Verify receiver saw a good delivery with expected headers
    deliveries = client.get("/_accept/webhooks/deliveries").json()["deliveries"]
    assert len(deliveries) == 1
    hdrs = {k.lower(): v for k, v in deliveries[0]["headers"].items()}
    assert hdrs.get("x-topic") == BASE_TOPIC
    assert hdrs.get("x-signature")  # present
    assert hdrs.get("x-attempt") == "2"  # second attempt after one failure
    assert hdrs.get("x-signature-alg") == "hmac-sha256"
    assert hdrs.get("x-signature-version") == "v1"
    assert hdrs.get("x-payload-version") == "1"


def test_a502_secret_rotation_accepts_old_and_new(client):
    # Configure receiver with two secrets (old + new), no failures
    old_secret = "old"
    new_secret = "new"
    client.post(
        "/_accept/webhooks/config", json={"secrets": [old_secret, new_secret], "fail_first": 0}
    )
    _subscribe(client, secret=old_secret)

    # Fire with payload; even though subscription holds old secret, verify_any accepts either
    outbox_id = _test_fire(client, {"x": 1})
    client.post("/scheduler/tick")
    assert _process_one(client) is True

    deliveries = client.get("/_accept/webhooks/deliveries").json()["deliveries"]
    assert len(deliveries) == 1
    # Now rotate subscription to new secret and send again
    _subscribe(client, secret=new_secret)
    outbox_id = _test_fire(client, {"x": 2})
    client.post("/scheduler/tick")
    assert _process_one(client) is True
    deliveries = client.get("/_accept/webhooks/deliveries").json()["deliveries"]
    assert len(deliveries) >= 2
