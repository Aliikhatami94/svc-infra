from __future__ import annotations

import time

from svc_infra.security.signed_cookies import sign_cookie, verify_cookie


def test_sign_and_verify_success():
    val = sign_cookie({"user": "u1", "scope": ["a", "b"]}, key="k1")
    ok, payload = verify_cookie(val, key="k1")
    assert ok and payload["user"] == "u1" and payload["scope"] == ["a", "b"]


def test_tamper_detection():
    val = sign_cookie({"n": 1}, key="secret")
    # flip a bit in body
    body, sig = val.split(".", 1)
    tampered_body = body[:-2] + ("A" if body[-1] != "A" else "B")
    bad = f"{tampered_body}.{sig}"
    ok, payload = verify_cookie(bad, key="secret")
    assert not ok and payload is None


def test_old_key_rotation():
    val = sign_cookie({"sub": "u"}, key="new")
    ok, _ = verify_cookie(val, key="new", old_keys=["old1", "old2"])  # should pass primary
    assert ok
    # A cookie signed with old key should pass when old_keys provided
    old_val = sign_cookie({"sub": "u"}, key="old1")
    ok2, _ = verify_cookie(old_val, key="new", old_keys=["old1", "old2"])  # verify using old
    assert ok2


def test_expiration():
    val = sign_cookie({"a": 1}, key="k", expires_in=1)
    ok, _ = verify_cookie(val, key="k")
    assert ok
    time.sleep(1.1)
    ok2, _ = verify_cookie(val, key="k")
    assert not ok2
