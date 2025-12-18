from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    from sqlalchemy import or_, select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover - optional import for type hints
    AsyncSession = Any  # type: ignore[misc,assignment]
    select = None  # type: ignore[assignment]
    or_ = None  # type: ignore[assignment]

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
    next_allowed_at: datetime | None
    failure_count: int


# ---------------- Pure calculation -----------------


def compute_lockout(
    fail_count: int, *, cfg: LockoutConfig, now: datetime | None = None
) -> LockoutStatus:
    now = now or datetime.now(UTC)
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
    user_id: uuid.UUID | None,
    ip_hash: str | None,
    success: bool,
) -> None:
    attempt = FailedAuthAttempt(user_id=user_id, ip_hash=ip_hash, success=success)
    session.add(attempt)
    await session.flush()


async def get_lockout_status(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    ip_hash: str | None,
    cfg: LockoutConfig | None = None,
) -> LockoutStatus:
    cfg = cfg or LockoutConfig()
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=cfg.window_minutes)

    q = select(FailedAuthAttempt).where(
        FailedAuthAttempt.ts >= window_start,
        FailedAuthAttempt.success == False,  # noqa: E712
    )
    # Use OR logic: lock out if EITHER user_id OR ip_hash has too many failures
    # This prevents attackers from rotating IPs to bypass lockout
    filters = []
    if user_id:
        filters.append(FailedAuthAttempt.user_id == user_id)
    if ip_hash:
        filters.append(FailedAuthAttempt.ip_hash == ip_hash)
    if filters:
        q = q.where(or_(*filters))

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
