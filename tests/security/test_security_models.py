from __future__ import annotations

import uuid
from datetime import datetime, timezone

from svc_infra.security.models import (
    compute_audit_hash,
    generate_refresh_token,
    hash_refresh_token,
    rotate_refresh_token,
)


def test_refresh_token_generation_and_hash():
    raw = generate_refresh_token()
    assert isinstance(raw, str)
    assert len(raw) == 64  # two UUID4 hex concatenated
    h = hash_refresh_token(raw)
    assert len(h) == 64
    new_raw, new_hash, expires_at = rotate_refresh_token(h)
    assert new_raw != raw
    assert new_hash != h
    assert expires_at > datetime.now(timezone.utc)


def test_audit_hash_chain_continuity():
    actor = uuid.uuid4()
    tenant = "tenantA"
    ts1 = datetime.now(timezone.utc)

    h1 = compute_audit_hash(
        None,
        ts=ts1,
        actor_id=actor,
        tenant_id=tenant,
        event_type="login",
        resource_ref=None,
        metadata={"ip": "1.1.1.1"},
    )
    ts2 = datetime.now(timezone.utc)
    h2 = compute_audit_hash(
        h1,
        ts=ts2,
        actor_id=actor,
        tenant_id=tenant,
        event_type="refresh",
        resource_ref=None,
        metadata={"count": 1},
    )
    ts3 = datetime.now(timezone.utc)
    h3 = compute_audit_hash(
        h2,
        ts=ts3,
        actor_id=actor,
        tenant_id=tenant,
        event_type="logout",
        resource_ref=None,
        metadata={"reason": "user_initiated"},
    )

    # Recompute chain to verify integrity
    h1_r = compute_audit_hash(
        None,
        ts=ts1,
        actor_id=actor,
        tenant_id=tenant,
        event_type="login",
        resource_ref=None,
        metadata={"ip": "1.1.1.1"},
    )
    assert h1_r == h1
    h2_r = compute_audit_hash(
        h1,
        ts=ts2,
        actor_id=actor,
        tenant_id=tenant,
        event_type="refresh",
        resource_ref=None,
        metadata={"count": 1},
    )
    assert h2_r == h2
    h3_r = compute_audit_hash(
        h2,
        ts=ts3,
        actor_id=actor,
        tenant_id=tenant,
        event_type="logout",
        resource_ref=None,
        metadata={"reason": "user_initiated"},
    )
    assert h3_r == h3
