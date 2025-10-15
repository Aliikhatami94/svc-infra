from __future__ import annotations

from typing import Iterable, Optional

from svc_infra.db.outbox import OutboxStore
from svc_infra.jobs.queue import JobQueue


def make_outbox_tick(
    outbox: OutboxStore,
    queue: JobQueue,
    *,
    topics: Optional[Iterable[str]] = None,
    job_name_prefix: str = "outbox",
):
    """Return an async task function to move one outbox message into the job queue.

    - It fetches at most one unprocessed message per tick to avoid starving others.
    - The enqueued job name is f"{job_name_prefix}.{topic}" to allow routing.
    - The job payload contains `outbox_id`, `topic`, and original `payload`.
    """

    dispatched: set[int] = set()

    async def _tick():
        # Outbox is sync; this wrapper is async for scheduler compatibility
        msg = outbox.fetch_next(topics=topics)
        if not msg:
            return
        if msg.id in dispatched:
            return
        job_name = f"{job_name_prefix}.{msg.topic}"
        queue.enqueue(job_name, {"outbox_id": msg.id, "topic": msg.topic, "payload": msg.payload})
        # mark as dispatched (bump attempts) so it won't be re-enqueued by fetch_next
        outbox.mark_failed(msg.id)
        dispatched.add(msg.id)

    return _tick
