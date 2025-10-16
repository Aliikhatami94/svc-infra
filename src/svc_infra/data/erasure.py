from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, Protocol


class SqlSession(Protocol):  # minimal protocol for tests/integration
    async def execute(self, stmt: Any) -> Any:
        pass


@dataclass(frozen=True)
class ErasureStep:
    name: str
    run: Callable[[SqlSession, str], Awaitable[int] | int]


@dataclass(frozen=True)
class ErasurePlan:
    steps: Iterable[ErasureStep]


async def run_erasure(
    session: SqlSession,
    principal_id: str,
    plan: ErasurePlan,
    *,
    on_audit: Optional[Callable[[str, dict[str, Any]], None]] = None,
) -> int:
    """Run an erasure plan and optionally emit an audit event.

    Returns total affected rows across steps.
    """
    total = 0
    for s in plan.steps:
        res = s.run(session, principal_id)
        if hasattr(res, "__await__"):
            res = await res  # type: ignore[misc]
        total += int(res or 0)
    if on_audit:
        on_audit("erasure.completed", {"principal_id": principal_id, "affected": total})
    return total


__all__ = ["ErasureStep", "ErasurePlan", "run_erasure"]
