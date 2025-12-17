from __future__ import annotations

import uuid

import pytest


@pytest.mark.acceptance
class TestRateLimitingAcceptance:
    def test_dependency_rate_limit_429_and_retry_after(self, client):
        # Hit /rl/dep 4 times; limit is 3 per minute using a unique key per run
        unique_key = f"rl-accept-test-{uuid.uuid4().hex[:8]}"
        headers = {"X-RL-Key": unique_key}
        r1 = client.get("/rl/dep", headers=headers)
        r2 = client.get("/rl/dep", headers=headers)
        r3 = client.get("/rl/dep", headers=headers)
        r4 = client.get("/rl/dep", headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200
        assert r4.status_code == 429
        assert r4.headers.get("Retry-After") is not None

    def test_middleware_rate_limit_headers_present(self, client):
        # Global SimpleRateLimitMiddleware is active; it uses X-API-Key or client IP as key.
        # Use a distinct X-API-Key so this test is isolated.
        headers = {"X-API-Key": "accept-test-key"}
        r = client.get("/ping", headers=headers)
        # Success response should include RL headers
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Limit") is not None
        assert r.headers.get("X-RateLimit-Remaining") is not None
        assert r.headers.get("X-RateLimit-Reset") is not None

        # Now exceed the limit quickly by reusing same key if the default limit/window are small enough.
        # We don't assume the global limit; just ensure headers present on success. The 429 path
        # itself is exercised in unit tests; acceptance focuses on integration presence.
