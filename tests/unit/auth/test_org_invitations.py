from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from svc_infra.security.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from svc_infra.security.org_invites import (
    accept_invitation,
    issue_invitation,
    resend_invitation,
)


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_issue_resend_accept_invitation():
    db = FakeDB()
    org = Organization(id=uuid.uuid4(), name="Acme")
    db.add(org)

    # issue
    raw1, inv1 = await issue_invitation(db, org_id=org.id, email="User@Email.com", role="member")
    assert isinstance(raw1, str) and len(raw1) >= 64
    assert isinstance(inv1, OrganizationInvitation)
    assert inv1.email == "user@email.com"
    assert inv1.revoked_at is None and inv1.used_at is None

    # issue again for the same email auto-revokes previous and creates a new one
    raw2, inv2 = await issue_invitation(db, org_id=org.id, email="user@email.com", role="member")
    assert inv1.revoked_at is not None
    assert inv2.revoked_at is None
    assert raw2 != raw1

    # resend updates token and timestamps
    raw3 = await resend_invitation(db, invitation=inv2)
    assert raw3 != raw2
    assert inv2.resend_count == 1
    assert inv2.last_sent_at is not None

    # accept creates a membership
    user_id = uuid.uuid4()
    mem = await accept_invitation(db, invitation=inv2, user_id=user_id)
    assert isinstance(mem, OrganizationMembership)
    assert mem.org_id == org.id and mem.user_id == user_id
    assert inv2.used_at is not None


@pytest.mark.asyncio
async def test_invitation_expiry_and_revocation():
    db = FakeDB()
    org = Organization(id=uuid.uuid4(), name="Beta")
    db.add(org)

    # Create an already-expired invitation
    _raw, inv = await issue_invitation(db, org_id=org.id, email="a@b.com", role="admin")
    inv.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(ValueError):
        await accept_invitation(db, invitation=inv, user_id=uuid.uuid4())

    # Revoked invitation
    _raw2, inv2 = await issue_invitation(db, org_id=org.id, email="c@d.com", role="admin")
    inv2.revoked_at = datetime.now(UTC)
    with pytest.raises(ValueError):
        await accept_invitation(db, invitation=inv2, user_id=uuid.uuid4())
