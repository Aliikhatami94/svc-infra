from __future__ import annotations

import os

from redis import Redis

from .queue import InMemoryJobQueue, JobQueue
from .redis_queue import RedisJobQueue
from .scheduler import InMemoryScheduler


class JobsConfig:
    def __init__(self, driver: str | None = None):
        # Future: support redis/sql drivers via extras
        self.driver = driver or os.getenv("JOBS_DRIVER", "memory").lower()


def easy_jobs(*, driver: str | None = None) -> tuple[JobQueue, InMemoryScheduler]:
    """One-call wiring for jobs: returns (queue, scheduler).

    Defaults to in-memory implementations for local/dev. ENV override via JOBS_DRIVER.
    """
    cfg = JobsConfig(driver=driver)
    # Choose backend
    if cfg.driver == "redis":
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = Redis.from_url(url)
        queue = RedisJobQueue(client)
    else:
        queue = InMemoryJobQueue()
    scheduler = InMemoryScheduler()
    return queue, scheduler
