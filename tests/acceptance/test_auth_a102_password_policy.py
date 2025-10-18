from __future__ import annotations

import pytest
from starlette.testclient import TestClient

pytestmark = [pytest.mark.acceptance, pytest.mark.security]


@pytest.fixture()
def local_client(_acceptance_app_ready):
    with TestClient(_acceptance_app_ready) as c:
        yield c


def test_a102_reject_common_or_weak_passwords(local_client: TestClient):
    # Too short and common
    r = local_client.post(
        "/auth/register",
        json={"email": "weak1@example.com", "password": "password"},
    )
    assert r.status_code == 400, r.text
    reasons = r.json().get("reasons") or []
    # Expect at least min_length and common_password; symbols/digit/upper/lower may also be present
    assert any(s.startswith("min_length(") for s in reasons)
    assert "common_password" in reasons

    # Missing classes: no upper, no digit, no symbol
    r2 = local_client.post(
        "/auth/register",
        json={"email": "weak2@example.com", "password": "alllowerletters"},
    )
    assert r2.status_code == 400, r2.text
    reasons2 = r2.json().get("reasons") or []
    assert "missing_upper" in reasons2
    assert "missing_digit" in reasons2
    assert "missing_symbol" in reasons2

    # Happy path still works with a strong password
    r3 = local_client.post(
        "/auth/register",
        json={"email": "strong@example.com", "password": "P@ssw0rd!1234"},
    )
    assert r3.status_code == 201, r3.text
    token = r3.json().get("verify_token")
    assert token
