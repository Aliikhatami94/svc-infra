from __future__ import annotations

import asyncio
import contextlib
from typing import Awaitable, Callable, Optional

from .queue import JobQueue

ProcessFunc = Callable[[object], Awaitable[None]]


class WorkerRunner:
    """Cooperative worker loop with graceful stop.

    - start(): begin polling the queue and processing jobs
    - stop(grace_seconds): signal stop, wait up to grace for current job to finish
    """

    def __init__(self, queue: JobQueue, handler: ProcessFunc, *, poll_interval: float = 0.25):
        self._queue = queue
        self._handler = handler
        self._poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._inflight: Optional[asyncio.Task] = None

    async def _loop(self) -> None:
        try:
            while not self._stopping.is_set():
                job = self._queue.reserve_next()
                if not job:
                    await asyncio.sleep(self._poll_interval)
                    continue

                # Process one job; track in-flight task for stop()
                async def _run():
                    try:
                        await self._handler(job)
                    except Exception as exc:  # pragma: no cover
                        self._queue.fail(job.id, error=str(exc))
                        return
                    self._queue.ack(job.id)

                self._inflight = asyncio.create_task(_run())
                try:
                    await self._inflight
                finally:
                    self._inflight = None
        finally:
            # exiting loop
            pass

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        return self._task

    async def stop(self, *, grace_seconds: float = 10.0) -> None:
        self._stopping.set()
        # Wait for in-flight job to complete, up to grace
        if self._inflight is not None and not self._inflight.done():
            try:
                await asyncio.wait_for(self._inflight, timeout=grace_seconds)
            except asyncio.TimeoutError:
                # Give up; job will be retried if your queue supports visibility timeouts
                pass
        # Finally, wait for loop to exit (should be quick since stopping is set)
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=max(0.1, self._poll_interval + 0.1))
            except asyncio.TimeoutError:
                # Cancel as a last resort
                self._task.cancel()
                with contextlib.suppress(Exception):
                    await self._task
