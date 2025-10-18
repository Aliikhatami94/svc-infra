from __future__ import annotations

import pytest


@pytest.mark.acceptance
def test_ping_smoke(client):
    r = client.get("/ping")
    assert r.status_code == 200
