from __future__ import annotations

import uuid

import pytest

from svc_infra.security.audit import append_audit_event, verify_audit_chain


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_audit_chain_verification_and_tamper_detection():
    db = FakeDB()
    tenant_id = "t1"
    actor_id = uuid.uuid4()

    # Build a chain of three events
    e1 = await append_audit_event(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type="login",
        metadata={"ip": "1.1.1.1"},
    )
    e2 = await append_audit_event(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type="update_profile",
        metadata={"field": "name"},
        prev_event=e1,
    )
    e3 = await append_audit_event(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type="logout",
        metadata={},
        prev_event=e2,
    )

    ok_chain, broken = verify_audit_chain([e1, e2, e3])
    assert ok_chain is True
    assert broken == []

    # Tamper with middle event metadata
    e2.event_metadata["field"] = "hacked"
    # Recompute chain verification
    ok_after, broken_after = verify_audit_chain([e1, e2, e3])
    assert ok_after is False
    # Middle event should be reported broken; subsequent may also appear if link is compromised
    assert 1 in broken_after
