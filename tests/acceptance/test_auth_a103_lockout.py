from __future__ import annotations

import pytest
from starlette.testclient import TestClient

pytestmark = [pytest.mark.acceptance, pytest.mark.security]


@pytest.fixture()
def local_client(_acceptance_app_ready):
    with TestClient(_acceptance_app_ready) as c:
        yield c


def test_a103_lockout_after_failed_attempts(local_client: TestClient):
    email = "lock@example.com"
    good_pw = "P@ssw0rd!1234"

    # Register and verify
    r = local_client.post("/auth/register", json={"email": email, "password": good_pw})
    assert r.status_code == 201, r.text
    token = r.json().get("verify_token")
    assert token
    rv = local_client.get(f"/auth/verify?token={token}")
    assert rv.status_code == 200, rv.text

    # Fail attempts up to threshold-1
    for i in range(2):  # threshold is 3 in acceptance app
        bad = local_client.post(
            "/users/login",
            data={"username": email, "password": "wrong"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert bad.status_code == 400, bad.text

    # Next failure should trigger lockout
    last = local_client.post(
        "/users/login",
        data={"username": email, "password": "wrong-again"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert last.status_code == 429, last.text
    assert last.headers.get("Retry-After") is not None
    body = last.json()
    assert body.get("error") == "account_locked"
    assert isinstance(body.get("retry_after"), int)
    assert body.get("retry_after") > 0

    # Even correct password should be blocked while locked
    good = local_client.post(
        "/users/login",
        data={"username": email, "password": good_pw},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert good.status_code == 429, good.text
