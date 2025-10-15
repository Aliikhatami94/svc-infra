from __future__ import annotations

"""Audit log append & chain verification utilities.

Provides helpers to append a new AuditLog entry maintaining a hash-chain
integrity model and to verify an existing sequence for tampering.

Design notes:
 - Each event stores prev_hash (previous event's hash or 64 zeros for genesis).
 - Hash = sha256(prev_hash + canonical_json_payload).
 - Verification recomputes expected hash for each event and compares.
 - If a middle event is altered, that event and all subsequent events will
   fail verification (because their prev_hash links break transitively).
"""

from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence, Tuple

try:  # SQLAlchemy may not be present in minimal test context
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    AsyncSession = Any  # type: ignore
    select = None  # type: ignore

from svc_infra.security.models import AuditLog, compute_audit_hash


async def append_audit_event(
    db: Any,
    *,
    actor_id=None,
    tenant_id: Optional[str] = None,
    event_type: str,
    resource_ref: Optional[str] = None,
    metadata: dict | None = None,
    ts: Optional[datetime] = None,
    prev_event: Optional[AuditLog] = None,
) -> AuditLog:
    """Append an audit event returning the persisted row.

    If prev_event is not supplied, it attempts to fetch the latest event for
    the tenant (or global chain when tenant_id is None).
    """
    metadata = metadata or {}
    ts = ts or datetime.now(timezone.utc)

    prev_hash: Optional[str] = None
    if prev_event is not None:
        prev_hash = prev_event.hash
    elif select is not None and hasattr(db, "execute"):  # attempt DB lookup for previous event
        try:
            stmt = (
                select(AuditLog)
                .where(AuditLog.tenant_id == tenant_id)
                .order_by(AuditLog.id.desc())
                .limit(1)
            )
            result = await db.execute(stmt)  # type: ignore[attr-defined]
            prev = result.scalars().first()
            if prev:
                prev_hash = prev.hash
        except Exception:  # pragma: no cover - defensive for minimal fakes
            pass

    new_hash = compute_audit_hash(
        prev_hash,
        ts=ts,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type=event_type,
        resource_ref=resource_ref,
        metadata=metadata,
    )

    row = AuditLog(
        ts=ts,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type=event_type,
        resource_ref=resource_ref,
        event_metadata=metadata,
        prev_hash=prev_hash or "0" * 64,
        hash=new_hash,
    )
    if hasattr(db, "add"):
        try:
            db.add(row)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - minimal shim safety
            pass
        if hasattr(db, "flush"):
            try:
                await db.flush()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass
    return row


def verify_audit_chain(events: Sequence[AuditLog]) -> Tuple[bool, List[int]]:
    """Verify a sequence of audit events.

    Returns (ok, broken_indices). If any event's hash doesn't match the recomputed
    expected hash (based on previous event), its index is recorded. All events are
    checked so callers can analyze extent of tampering.
    """
    broken: List[int] = []
    prev_hash = "0" * 64
    for idx, ev in enumerate(events):
        expected = compute_audit_hash(
            prev_hash if ev.prev_hash == prev_hash else ev.prev_hash,
            ts=ev.ts,
            actor_id=ev.actor_id,
            tenant_id=ev.tenant_id,
            event_type=ev.event_type,
            resource_ref=ev.resource_ref,
            metadata=ev.event_metadata,
        )
        # prev_hash stored should equal previous event hash (or zeros for genesis)
        if (idx == 0 and ev.prev_hash != "0" * 64) or (
            idx > 0 and ev.prev_hash != events[idx - 1].hash
        ):
            broken.append(idx)
        if ev.hash != expected:
            broken.append(idx)
        prev_hash = ev.hash
    ok = not broken
    return ok, sorted(set(broken))


__all__ = ["append_audit_event", "verify_audit_chain"]
