import pytest

from svc_infra.webhooks.signing import sign, verify

pytestmark = pytest.mark.webhooks


def test_sign_and_verify():
    payload = {"a": 1, "b": 2}
    secret = "sekrit"
    s = sign(secret, payload)
    assert isinstance(s, str)
    assert verify(secret, payload, s) is True
    assert verify(secret, payload, s + "x") is False
