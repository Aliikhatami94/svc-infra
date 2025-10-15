import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from svc_infra.webhooks.fastapi import require_signature
from svc_infra.webhooks.signing import sign

pytestmark = pytest.mark.webhooks


def test_require_signature_single_secret():
    app = FastAPI()

    def get_secret():
        return "sekrit"

    @app.post("/hook")
    def hook(body=Depends(require_signature(get_secret))):
        return {"ok": True}

    client = TestClient(app)

    payload = {"a": 1}
    sig = sign("sekrit", payload)
    r = client.post("/hook", json=payload, headers={"X-Signature": sig})
    assert r.status_code == 200
    # bad signature
    r2 = client.post("/hook", json=payload, headers={"X-Signature": sig + "x"})
    assert r2.status_code == 401


def test_require_signature_multiple_secrets():
    app = FastAPI()

    def get_secrets():
        return ["old", "new"]

    @app.post("/hook")
    def hook(body=Depends(require_signature(get_secrets))):
        return {"ok": True}

    client = TestClient(app)

    payload = {"x": 42}
    sig = sign("old", payload)
    r = client.post("/hook", json=payload, headers={"X-Signature": sig})
    assert r.status_code == 200
