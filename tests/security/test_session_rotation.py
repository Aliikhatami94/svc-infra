from __future__ import annotations

import uuid

import pytest

from svc_infra.security.models import AuthSession, RefreshToken
from svc_infra.security.session import issue_session_and_refresh, rotate_session_refresh


class FakeDB:
    def __init__(self):
        self.added = []

    async def flush(self):
        pass

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_issue_and_rotate_session():
    db = FakeDB()
    user_id = uuid.uuid4()
    raw, rt = await issue_session_and_refresh(db, user_id=user_id)
    assert isinstance(raw, str) and len(raw) == 64
    assert isinstance(rt, RefreshToken)
    # Ensure objects recorded
    assert any(isinstance(o, AuthSession) for o in db.added)
    assert any(isinstance(o, RefreshToken) for o in db.added)
    new_raw, new_rt = await rotate_session_refresh(db, current=rt)
    assert new_raw != raw
    assert new_rt.token_hash != rt.token_hash
