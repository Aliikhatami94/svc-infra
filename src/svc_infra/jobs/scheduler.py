from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict

CronFunc = Callable[[], Awaitable[None]]


@dataclass
class ScheduledTask:
    name: str
    interval_seconds: int
    func: CronFunc
    next_run_at: datetime


class InMemoryScheduler:
    """Interval-based scheduler for simple periodic tasks (tests/local).

    Not a full cron parser. Tracks next_run_at per task.
    """

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}

    def add_task(self, name: str, interval_seconds: int, func: CronFunc) -> None:
        now = datetime.now(timezone.utc)
        self._tasks[name] = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            func=func,
            next_run_at=now + timedelta(seconds=interval_seconds),
        )

    async def tick(self) -> None:
        now = datetime.now(timezone.utc)
        for task in self._tasks.values():
            if task.next_run_at <= now:
                await task.func()
                task.next_run_at = now + timedelta(seconds=task.interval_seconds)
