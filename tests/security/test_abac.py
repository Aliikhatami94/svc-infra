from __future__ import annotations

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.auth.security import Identity, Principal
from svc_infra.security.permissions import (
    PERMISSION_REGISTRY,
    RequireABAC,
    enforce_abac,
    owns_resource,
)


class Doc:
    def __init__(self, owner_id):
        self.id = uuid.uuid4()
        self.owner_id = owner_id


class U:
    def __init__(self, id, roles):
        self.id = id
        self.roles = roles


def test_enforce_abac_sync_ok_and_forbidden():
    uid = uuid.uuid4()
    p = Principal(user=U(uid, roles=["admin"]), scopes=[], via="jwt")
    # ensure admin has doc.read in registry for this test
    PERMISSION_REGISTRY.setdefault("admin", set()).add("doc.read")
    d_ok = Doc(owner_id=uid)
    d_bad = Doc(owner_id=uuid.uuid4())

    # ok path
    enforce_abac(p, permission="doc.read", resource=d_ok, predicate=owns_resource())

    # forbidden path
    with pytest.raises(Exception) as exc:
        enforce_abac(p, permission="doc.read", resource=d_bad, predicate=owns_resource())
    assert "forbidden" in str(exc.value)


def test_require_abac_dependency():
    uid = uuid.uuid4()
    PERMISSION_REGISTRY.setdefault("admin", set()).add("doc.read")

    def load_doc():
        return Doc(owner_id=uid)

    app = FastAPI()

    @app.get(
        "/docs/{doc_id}",
        dependencies=[
            RequireABAC(
                permission="doc.read",
                predicate=owns_resource(),
                resource_getter=load_doc,
            )
        ],
    )
    async def get_doc(identity: Identity, doc=Depends(load_doc)):
        return {"id": str(doc.id)}

    client = TestClient(app)

    # build principal injection via dependency override
    def override_identity():
        return Principal(user=U(uid, roles=["admin"]), scopes=[], via="jwt")

    from svc_infra.api.fastapi.auth import security as secmod

    app.dependency_overrides[secmod._current_principal] = override_identity

    r = client.get(f"/docs/{uuid.uuid4()}")
    assert r.status_code == 200
