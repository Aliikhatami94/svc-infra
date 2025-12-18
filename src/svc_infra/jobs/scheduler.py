from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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

    def __init__(self, tick_interval: float = 60.0):
        self._tasks: dict[str, ScheduledTask] = {}
        self._tick_interval = tick_interval

    def add_task(self, name: str, interval_seconds: int, func: CronFunc) -> None:
        now = datetime.now(UTC)
        self._tasks[name] = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            func=func,
            next_run_at=now + timedelta(seconds=interval_seconds),
        )

    async def tick(self) -> None:
        now = datetime.now(UTC)
        for task in self._tasks.values():
            if task.next_run_at <= now:
                await task.func()
                task.next_run_at = now + timedelta(seconds=task.interval_seconds)

    async def run(self) -> None:
        """Run the scheduler loop indefinitely.

        Calls tick() at regular intervals to check and execute due tasks.
        This method runs forever until cancelled.
        """
        while True:
            await self.tick()
            await asyncio.sleep(self._tick_interval)
