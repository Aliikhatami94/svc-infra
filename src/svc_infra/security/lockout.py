from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover - optional import for type hints
    AsyncSession = Any  # type: ignore[misc]
    select = None  # type: ignore

from svc_infra.security.models import FailedAuthAttempt


@dataclass
class LockoutConfig:
    threshold: int = 5  # failures before cooldown starts
    window_minutes: int = 15  # look-back window for counting failures
    base_cooldown_seconds: int = 30  # initial cooldown once threshold reached
    max_cooldown_seconds: int = 3600  # cap exponential growth at 1 hour


@dataclass
class LockoutStatus:
    locked: bool
    next_allowed_at: Optional[datetime]
    failure_count: int


# ---------------- Pure calculation -----------------


def compute_lockout(
    fail_count: int, *, cfg: LockoutConfig, now: Optional[datetime] = None
) -> LockoutStatus:
    now = now or datetime.now(timezone.utc)
    if fail_count < cfg.threshold:
        return LockoutStatus(False, None, fail_count)
    # cooldown factor exponent = fail_count - threshold
    exponent = fail_count - cfg.threshold
    cooldown = cfg.base_cooldown_seconds * (2**exponent)
    if cooldown > cfg.max_cooldown_seconds:
        cooldown = cfg.max_cooldown_seconds
    return LockoutStatus(True, now + timedelta(seconds=cooldown), fail_count)


# ---------------- Persistence helpers (async) ---------------


async def record_attempt(
    session: AsyncSession,
    *,
    user_id: Optional[uuid.UUID],
    ip_hash: Optional[str],
    success: bool,
) -> None:
    attempt = FailedAuthAttempt(user_id=user_id, ip_hash=ip_hash, success=success)
    session.add(attempt)
    await session.flush()


async def get_lockout_status(
    session: AsyncSession,
    *,
    user_id: Optional[uuid.UUID],
    ip_hash: Optional[str],
    cfg: Optional[LockoutConfig] = None,
) -> LockoutStatus:
    cfg = cfg or LockoutConfig()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=cfg.window_minutes)

    q = select(FailedAuthAttempt).where(
        FailedAuthAttempt.ts >= window_start,
        FailedAuthAttempt.success == False,  # noqa: E712
    )
    if user_id:
        q = q.where(FailedAuthAttempt.user_id == user_id)
    if ip_hash:
        q = q.where(FailedAuthAttempt.ip_hash == ip_hash)

    rows: Sequence[FailedAuthAttempt] = (await session.execute(q)).scalars().all()
    fail_count = len(rows)
    return compute_lockout(fail_count, cfg=cfg, now=now)


__all__ = [
    "LockoutConfig",
    "LockoutStatus",
    "compute_lockout",
    "record_attempt",
    "get_lockout_status",
]
