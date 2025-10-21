from __future__ import annotations

import json
import uuid

import pytest


@pytest.mark.acceptance
@pytest.mark.concurrency
class TestIdempotencyAcceptance:
    def test_idempotent_replay_same_payload(self, client):
        url = "/idmp/echo"
        key = "idem-abc-1"
        payload = {"a": 1, "b": {"c": 2}}
        # First request
        r1 = client.post(url, headers={"Idempotency-Key": key}, json=payload)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["ok"] is True
        assert b1["echo"] == payload
        assert "nonce" in b1
        # Second request with same key and same payload → replay identical body
        r2 = client.post(url, headers={"Idempotency-Key": key}, json=payload)
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2 == b1

    def test_idempotent_conflict_on_mismatch(self, client):
        url = "/idmp/echo"
        key = "idem-abc-2"
        payload1 = {"x": 1}
        payload2 = {"x": 2}
        r1 = client.post(url, headers={"Idempotency-Key": key}, json=payload1)
        assert r1.status_code == 200
        # Reuse key with different payload → 409 Conflict
        r2 = client.post(url, headers={"Idempotency-Key": key}, json=payload2)
        assert r2.status_code == 409
        body = r2.json()
        assert body.get("title") == "Conflict"
        assert "Idempotency-Key" in json.dumps(body).replace("-", "-")


@pytest.mark.acceptance
@pytest.mark.concurrency
class TestOptimisticLockingAcceptance:
    def test_version_mismatch_conflict(self, client):
        # Create an item
        item_id = uuid.uuid4().hex
        r_create = client.post("/cc/items", json={"id": item_id, "value": "a"})
        assert r_create.status_code == 201, r_create.text
        data = r_create.json()
        assert data["version"] == 1
        # Update with correct version → success
        r_ok = client.put(f"/cc/items/{item_id}", json={"value": "b", "version": 1})
        assert r_ok.status_code == 200, r_ok.text
        data2 = r_ok.json()
        assert data2["version"] == 2
        # Update with stale version → 409
        r_conflict = client.put(f"/cc/items/{item_id}", json={"value": "c", "version": 1})
        assert r_conflict.status_code == 409
        j = r_conflict.json()
        assert j.get("title") == "Conflict"
        assert j.get("detail") == "Version mismatch"
        assert j.get("expected") == 2
