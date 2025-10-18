from __future__ import annotations

import pytest
from starlette.testclient import TestClient

pytestmark = [pytest.mark.acceptance, pytest.mark.security]


@pytest.fixture()
def local_client(_acceptance_app_ready):
    with TestClient(_acceptance_app_ready) as c:
        yield c


def test_a101_register_verify_login_me(local_client: TestClient):
    # 1) register
    r = local_client.post(
        "/auth/register",
        json={"email": "a1@example.com", "password": "P@ssw0rd!1234"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    verify_token = body.get("verify_token")
    assert verify_token

    # 2) verify
    r2 = local_client.get(f"/auth/verify?token={verify_token}")
    assert r2.status_code == 200, r2.text

    # 3) login
    r3 = local_client.post(
        "/users/login",
        data={"username": "a1@example.com", "password": "P@ssw0rd!1234"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r3.status_code == 200, r3.text
    access = r3.json().get("access_token")
    assert access

    # 4) /auth/me with bearer token
    r4 = local_client.get("/auth/me", headers={"authorization": f"Bearer {access}"})
    assert r4.status_code == 200, r4.text
    me = r4.json()
    assert me["email"] == "a1@example.com"
    assert me["is_verified"] is True
