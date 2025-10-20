from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.acceptance


def test_a401_job_enqueue_and_process(client):
    # Ensure clean state
    client.post("/jobs/config/failures", json={"name": "a4.test", "times": 0})
    # Enqueue
    r = client.post("/jobs/enqueue", json={"name": "a4.test", "payload": {"x": 1}})
    assert r.status_code == 200
    jid = r.json()["id"]
    # Process one
    r = client.post("/jobs/process-one")
    assert r.status_code == 200 and r.json()["processed"] is True
    # Check results
    r = client.get("/jobs/results")
    results = r.json()["results"]
    assert any(res["id"] == jid and res["name"] == "a4.test" for res in results)


def test_a402_retry_and_backoff(client):
    # Configure handler to fail first attempt
    client.post("/jobs/config/failures", json={"name": "a4.fail", "times": 1})
    # Enqueue with tiny backoff for fast test
    r = client.post(
        "/jobs/enqueue",
        json={"name": "a4.fail", "payload": {"y": 2}, "backoff_seconds": 1},
    )
    jid = r.json()["id"]
    # First process → should fail and schedule retry in ~1s
    r = client.post("/jobs/process-one")
    assert r.status_code == 200 and r.json()["processed"] is True
    # Immediately processing again should find none due to backoff
    r = client.post("/jobs/process-one")
    assert r.status_code == 200 and r.json()["processed"] is False
    # Force due time to now for determinism
    client.post("/jobs/make-due", json={"id": jid})
    # Process again → should succeed on second attempt
    r = client.post("/jobs/process-one")
    assert r.status_code == 200 and r.json()["processed"] is True
    # Verify attempts recorded >= 2 for this job id
    res = client.get("/jobs/results").json()["results"]
    got = [x for x in res if x["id"] == jid]
    assert got and got[0]["attempts"] >= 2


def test_a403_scheduler_ticks_tasks(client):
    # Add a scheduler task with 0-second interval to be runnable immediately
    r = client.post("/scheduler/add", json={"name": "tick.me", "interval_seconds": 0})
    assert r.status_code == 200
    # Initial tick should run it once
    r = client.post("/scheduler/tick")
    assert r.status_code == 200
    # Tick a couple more times to increase the counter
    client.post("/scheduler/tick")
    client.post("/scheduler/tick")
    counters = client.get("/scheduler/counters").json()["counters"]
    assert counters.get("tick.me", 0) >= 3
