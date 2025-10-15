from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

try:  # optional SQLAlchemy import for environments without SA
    from sqlalchemy import select
except Exception:  # pragma: no cover
    select = None  # type: ignore

from .audit import append_audit_event, verify_audit_chain
from .models import AuditLog


async def append_event(
    db: Any,
    *,
    actor_id=None,
    tenant_id: Optional[str] = None,
    event_type: str,
    resource_ref: Optional[str] = None,
    metadata: dict | None = None,
    prev_event: Optional[AuditLog] = None,
) -> AuditLog:
    """Append an AuditLog event using the shared append utility.

    If prev_event is not provided, attempts to look up the last event for the tenant.
    """
    return await append_audit_event(
        db,
        actor_id=actor_id,
        tenant_id=tenant_id,
        event_type=event_type,
        resource_ref=resource_ref,
        metadata=metadata,
        prev_event=prev_event,
    )


async def verify_chain_for_tenant(
    db: Any, *, tenant_id: Optional[str] = None
) -> Tuple[bool, List[int]]:
    """Fetch all AuditLog events for a tenant and verify hash-chain integrity.

    Falls back to inspecting an in-memory 'added' list when SQLAlchemy is not available,
    to simplify unit tests with fake DBs.
    """
    events: Sequence[AuditLog] = []
    if select is not None and hasattr(db, "execute"):
        try:
            stmt = select(AuditLog)
            if tenant_id is not None:
                stmt = stmt.where(AuditLog.tenant_id == tenant_id)
            stmt = stmt.order_by(AuditLog.id.asc())
            result = await db.execute(stmt)  # type: ignore[attr-defined]
            events = list(result.scalars().all())
        except Exception:  # pragma: no cover
            events = []
    elif hasattr(db, "added"):
        try:
            pool = getattr(db, "added")
            # Preserve insertion order for in-memory fake DBs where primary keys may be None
            events = [
                e
                for e in pool
                if isinstance(e, AuditLog) and (tenant_id is None or e.tenant_id == tenant_id)
            ]
        except Exception:  # pragma: no cover
            events = []

    return verify_audit_chain(list(events))


__all__ = ["append_event", "verify_chain_for_tenant"]
