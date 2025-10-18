import uuid

import httpx
import pytest

pytestmark = pytest.mark.acceptance


def _auth_headers(token: str):
    return {"authorization": f"Bearer {token}"}


def register_verify_login(client: httpx.Client, email: str, password: str):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    token = r.json()["verify_token"]
    rv = client.get(f"/auth/verify?token={token}")
    assert rv.status_code == 200, rv.text
    lg = client.post(
        "/users/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert lg.status_code == 200, lg.text
    access = lg.json()["access_token"]
    return access


def test_a106_api_keys_lifecycle(client: httpx.Client):
    email = f"svc-{uuid.uuid4().hex[:8]}@example.com"
    pw = "P@ssw0rd!1234"

    token = register_verify_login(client, email, pw)

    # Create key (shows plaintext once)
    c = client.post(
        "/auth/keys",
        json={"name": "S2S", "scopes": ["payments:read"], "ttl_hours": 1},
        headers=_auth_headers(token),
    )
    assert c.status_code == 201, c.text
    body = c.json()
    assert body["key"] and body["key_prefix"].startswith("ak_")
    key_id = body["id"]

    # List keys (no plaintext)
    lst = client.get("/auth/keys", headers=_auth_headers(token))
    assert lst.status_code == 200, lst.text
    arr = lst.json()
    assert len(arr) >= 1
    assert arr[0]["key"] is None

    # Revoke
    rvk = client.post(f"/auth/keys/{key_id}/revoke", headers=_auth_headers(token))
    assert rvk.status_code == 204, rvk.text

    # Delete without force should now succeed since inactive
    dl = client.delete(f"/auth/keys/{key_id}", headers=_auth_headers(token))
    assert dl.status_code == 204, dl.text

    # Confirm it's gone
    lst2 = client.get("/auth/keys", headers=_auth_headers(token))
    assert all(x["id"] != key_id for x in lst2.json())
