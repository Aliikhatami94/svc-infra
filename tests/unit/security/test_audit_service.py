from __future__ import annotations

import uuid

import pytest

from svc_infra.security.audit import verify_audit_chain
from svc_infra.security.audit_service import append_event, verify_chain_for_tenant
from svc_infra.security.models import AuditLog


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_audit_service_append_and_verify():
    db = FakeDB()
    actor = uuid.uuid4()
    tenant = "tenant-a"

    e1 = await append_event(
        db, actor_id=actor, tenant_id=tenant, event_type="create", metadata={"x": 1}
    )
    e2 = await append_event(
        db,
        actor_id=actor,
        tenant_id=tenant,
        event_type="update",
        metadata={"x": 2},
        prev_event=e1,
    )
    # Link third event explicitly to keep a single continuous chain in this fake DB context
    await append_event(
        db,
        actor_id=actor,
        tenant_id=tenant,
        event_type="delete",
        metadata={},
        prev_event=e2,
    )

    ok, broken = await verify_chain_for_tenant(db, tenant_id=tenant)
    assert ok is True
    assert broken == []

    # Tamper with e2
    for ev in db.added:
        if isinstance(ev, AuditLog) and ev.event_type == "update":
            ev.event_metadata["x"] = 999

    ok2, broken2 = await verify_chain_for_tenant(db, tenant_id=tenant)
    # Service-level verify should detect tampering
    assert ok2 is False
    assert broken2  # at least one broken index

    # Also verify using the pure function on the in-memory sequence
    in_mem = [e for e in db.added if isinstance(e, AuditLog) and e.tenant_id == tenant]
    ok3, broken3 = verify_audit_chain(in_mem)
    assert ok3 is False
    assert broken3
