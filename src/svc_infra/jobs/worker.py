from __future__ import annotations

from typing import Awaitable, Callable

from .queue import Job, JobQueue

ProcessFunc = Callable[[Job], Awaitable[None]]


async def process_one(queue: JobQueue, handler: ProcessFunc) -> bool:
    """Reserve a job, process with handler, ack on success or fail with backoff.

    Returns True if a job was processed (success or fail), False if no job was available.
    """
    job = queue.reserve_next()
    if not job:
        return False
    try:
        await handler(job)
    except Exception as exc:  # pragma: no cover - exercise in tests by raising
        queue.fail(job.id, error=str(exc))
        return True
    queue.ack(job.id)
    return True
