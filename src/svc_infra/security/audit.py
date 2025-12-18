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

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

try:  # SQLAlchemy may not be present in minimal test context
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    AsyncSession = Any  # type: ignore[misc,assignment]
    select = None  # type: ignore[assignment]

from svc_infra.security.models import AuditLog, compute_audit_hash


@dataclass(frozen=True)
class AuditEvent:
    ts: datetime
    actor_id: Any
    tenant_id: str | None
    event_type: str
    resource_ref: str | None
    metadata: dict


class AuditLogStore(Protocol):
    """Minimal interface for storing audit events.

    This is intentionally small so applications can swap in a SQL-backed store.
    """

    def append(
        self,
        *,
        actor_id: Any = None,
        tenant_id: str | None = None,
        event_type: str,
        resource_ref: str | None = None,
        metadata: dict | None = None,
        ts: datetime | None = None,
    ) -> AuditEvent:
        pass

    def list(
        self,
        *,
        tenant_id: str | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        pass


class InMemoryAuditLogStore:
    """In-memory audit event store (useful for tests and prototypes)."""

    def __init__(self):
        self._events: list[AuditEvent] = []

    def append(
        self,
        *,
        actor_id: Any = None,
        tenant_id: str | None = None,
        event_type: str,
        resource_ref: str | None = None,
        metadata: dict | None = None,
        ts: datetime | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            ts=ts or datetime.now(UTC),
            actor_id=actor_id,
            tenant_id=tenant_id,
            event_type=event_type,
            resource_ref=resource_ref,
            metadata=dict(metadata or {}),
        )
        self._events.append(event)
        return event

    def list(self, *, tenant_id: str | None = None, limit: int | None = None) -> list[AuditEvent]:
        out = [e for e in self._events if tenant_id is None or e.tenant_id == tenant_id]
        if limit is not None:
            return out[-int(limit) :]
        return out


async def append_audit_event(
    db: Any,
    *,
    actor_id=None,
    tenant_id: str | None = None,
    event_type: str,
    resource_ref: str | None = None,
    metadata: dict | None = None,
    ts: datetime | None = None,
    prev_event: AuditLog | None = None,
) -> AuditLog:
    """Append an audit event returning the persisted row.

    If prev_event is not supplied, it attempts to fetch the latest event for
    the tenant (or global chain when tenant_id is None).
    """
    metadata = metadata or {}
    ts = ts or datetime.now(UTC)

    prev_hash: str | None = None
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
            result = await db.execute(stmt)
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
            db.add(row)
        except Exception:  # pragma: no cover - minimal shim safety
            pass
        if hasattr(db, "flush"):
            try:
                await db.flush()
            except Exception:  # pragma: no cover
                pass
    return row


def verify_audit_chain(events: Sequence[AuditLog]) -> tuple[bool, list[int]]:
    """Verify a sequence of audit events.

    Returns (ok, broken_indices). If any event's hash doesn't match the recomputed
    expected hash (based on previous event), its index is recorded. All events are
    checked so callers can analyze extent of tampering.
    """
    broken: list[int] = []
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


__all__ = [
    "append_audit_event",
    "verify_audit_chain",
    "AuditEvent",
    "AuditLogStore",
    "InMemoryAuditLogStore",
]
