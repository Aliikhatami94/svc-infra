from __future__ import annotations

import pytest


@pytest.mark.acceptance
class TestDataLifecycleAcceptance:
    def test_a701_fixtures_run_once(self, client):
        # First run should insert default user
        r1 = client.post("/data/fixtures/run-once")
        assert r1.status_code == 200
        users1 = r1.json()["users"]
        assert any(u["email"] == "alpha@example.com" for u in users1)

        # Second run should not duplicate
        r2 = client.post("/data/fixtures/run-once")
        assert r2.status_code == 200
        users2 = r2.json()["users"]
        emails = [u["email"] for u in users2]
        assert emails.count("alpha@example.com") == 1

    def test_a702_erasure_workflow(self, client):
        # Ensure the user exists
        client.post("/data/_reset")
        client.post("/data/fixtures/run-once")
        # Run erasure for u1
        e = client.post("/data/erasure/run", json={"principal_id": "u1"})
        assert e.status_code == 200
        assert e.json()["affected"] >= 0
        # Running again should be idempotent-ish (affected may be 0)
        e2 = client.post("/data/erasure/run", json={"principal_id": "u1"})
        assert e2.status_code == 200

    def test_a703_retention_purge_soft_then_hard(self, client):
        client.post("/data/_reset")
        # Soft-delete purge old records
        r_soft = client.post("/data/retention/purge", json={"days": 1, "hard": False})
        assert r_soft.status_code == 200
        body_soft = r_soft.json()
        assert body_soft["affected"] >= 1
        # Hard-delete purge old records (run again; soft-deleted now become deleted or nothing to do)
        r_hard = client.post("/data/retention/purge", json={"days": 1, "hard": True})
        assert r_hard.status_code == 200
