from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from svc_infra.api.fastapi.auth.routers.session_router import build_session_router
from svc_infra.security.models import AuthSession
from svc_infra.security.session import issue_session_and_refresh


class FakeUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.roles = ["admin"]  # maps to permissions including security.session.list/revoke


class FakeDB:
    def __init__(self):
        self.objects = []

    async def execute(self, stmt):  # minimal select mock
        class Result:
            def __init__(self, data):
                self._data = data

            def scalars(self):
                class S:
                    def __init__(self, data):
                        self._data = data

                    def all(self):
                        return [o for o in self._data if isinstance(o, AuthSession)]

                return S(self._data)

        return Result(self.objects)

    async def get(self, model, pk):
        for o in self.objects:
            if isinstance(o, model) and str(o.id) == str(pk):
                return o
        return None

    def add(self, obj):
        self.objects.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_list_and_revoke_session():
    db = FakeDB()
    user = FakeUser()
    raw, rt = await issue_session_and_refresh(db, user_id=user.id)
    # Build router and call list
    router = build_session_router()
    # Directly invoke underlying function (not full FastAPI app for brevity)
    list_fn = next(
        r.endpoint for r in router.routes if r.path == "/sessions/me" and r.methods == {"GET"}
    )
    revoke_fn = next(
        r.endpoint
        for r in router.routes
        if r.path == "/sessions/{session_id}/revoke" and r.methods == {"POST"}
    )

    class IdentityPrincipal:
        def __init__(self, user):
            self.user = user

    identity = IdentityPrincipal(user)
    sessions = await list_fn(identity=identity, session=db)
    assert len(sessions) == 1
    session_id = sessions[0]["id"]

    await revoke_fn(session_id=session_id, identity=identity, db=db)
    # Verify session revoked and refresh tokens cascade
    auth_session = await db.get(AuthSession, session_id)
    assert auth_session.revoked_at is not None
    assert all(rt.revoked_at is not None for rt in auth_session.refresh_tokens)


@pytest.mark.asyncio
async def test_cannot_revoke_other_users_session():
    db = FakeDB()
    owner = FakeUser()
    other = FakeUser()  # attacker / different principal
    raw, rt = await issue_session_and_refresh(db, user_id=owner.id)
    router = build_session_router()
    revoke_fn = next(
        r.endpoint
        for r in router.routes
        if r.path == "/sessions/{session_id}/revoke" and r.methods == {"POST"}
    )

    class IdentityPrincipal:
        def __init__(self, user):
            self.user = user

    owner_identity = IdentityPrincipal(owner)
    other_identity = IdentityPrincipal(other)

    # Owner can revoke (session id derived from rt.session)
    await revoke_fn(session_id=str(rt.session.id), identity=owner_identity, db=db)
    auth_session = await db.get(AuthSession, str(rt.session.id))
    assert auth_session.revoked_at is not None

    # Reset state for negative test (issue fresh session)
    db.objects = []
    raw2, rt2 = await issue_session_and_refresh(db, user_id=owner.id)
    # Attempt revoke by other user -> 403
    with pytest.raises(HTTPException) as exc:
        await revoke_fn(session_id=str(rt2.session.id), identity=other_identity, db=db)
    assert exc.value.status_code == 403
    assert "forbidden" in str(exc.value.detail)
    auth_session2 = await db.get(AuthSession, str(rt2.session.id))
    assert auth_session2.revoked_at is None
