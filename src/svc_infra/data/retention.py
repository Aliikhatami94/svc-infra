from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Protocol, Sequence


class SqlSession(Protocol):  # minimal protocol for tests/integration
    async def execute(self, stmt: Any) -> Any:
        pass


@dataclass(frozen=True)
class RetentionPolicy:
    name: str
    model: Any  # SQLAlchemy model or test double exposing columns
    older_than_days: int
    soft_delete_field: Optional[str] = "deleted_at"
    extra_where: Optional[Sequence[Any]] = None
    hard_delete: bool = False


async def purge_policy(session: SqlSession, policy: RetentionPolicy) -> int:
    """Execute a single retention purge according to policy.

    If hard_delete is False and soft_delete_field exists on model, set timestamp; else DELETE.
    Returns number of affected rows (best-effort; test doubles may return an int directly).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=policy.older_than_days)
    m = policy.model
    where = list(policy.extra_where or [])
    created_col = getattr(m, "created_at", None)
    if created_col is not None and hasattr(created_col, "__le__"):
        where.append(created_col <= cutoff)  # type: ignore[operator]

    # Soft-delete path when available and requested
    if not policy.hard_delete and policy.soft_delete_field and hasattr(m, policy.soft_delete_field):
        stmt = m.update().where(*where).values({policy.soft_delete_field: cutoff})  # type: ignore[attr-defined]
        res = await session.execute(stmt)
        return getattr(res, "rowcount", 0)

    # Hard delete fallback
    stmt = m.delete().where(*where)  # type: ignore[attr-defined]
    res = await session.execute(stmt)
    return getattr(res, "rowcount", 0)


async def run_retention_purge(session: SqlSession, policies: Iterable[RetentionPolicy]) -> int:
    total = 0
    for p in policies:
        total += await purge_policy(session, p)
    return total


__all__ = ["RetentionPolicy", "purge_policy", "run_retention_purge"]
