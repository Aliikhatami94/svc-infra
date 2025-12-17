from __future__ import annotations

import pytest


@pytest.mark.acceptance
class TestAbuseHeuristicsAcceptance:
    def test_rate_limit_metrics_hook_captures_events(self, client):
        # Enable capture hook
        r = client.post("/_accept/abuse/hooks/rate-limit/enable")
        assert r.status_code == 200 and r.json().get("enabled") is True

        # Trip dependency-based limiter 4 times (limit=3) to produce one 429.
        # Use a unique RL key so this test doesn't affect others.
        headers = {"X-RL-Key": "abuse-accept-test"}
        for _ in range(3):
            ok = client.get("/rl/dep", headers=headers)
            assert ok.status_code == 200
        too_many = client.get("/rl/dep", headers=headers)
        assert too_many.status_code == 429
        # sanity: Retry-After present (covered by RL tests as well)
        assert too_many.headers.get("Retry-After") is not None

        # Read captured events
        events_resp = client.get("/_accept/abuse/hooks/rate-limit/events")
        assert events_resp.status_code == 200
        events = events_resp.json().get("events") or []
        assert isinstance(events, list)
        # At least one event recorded with expected fields
        assert len(events) >= 1
        evt = events[-1]
        assert set(evt.keys()) == {"key", "limit", "retry_after"}
        assert evt["key"] == "abuse-accept-test"  # matches header-provided key
        assert int(evt["limit"]) == 3
        # retry_after should be >= 0 integer
        assert isinstance(evt["retry_after"], int)
        assert evt["retry_after"] >= 0

        # Disable capture hook
        r = client.post("/_accept/abuse/hooks/rate-limit/disable")
        assert r.status_code == 200 and r.json().get("enabled") is False
