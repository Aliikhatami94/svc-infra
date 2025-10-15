from __future__ import annotations

import asyncio
from typing import Optional

import typer

from svc_infra.jobs.easy import easy_jobs
from svc_infra.jobs.loader import schedule_from_env
from svc_infra.jobs.worker import process_one

app = typer.Typer(help="Background jobs and scheduler commands")


@app.command("run")
def run(
    poll_interval: float = typer.Option(0.5, help="Sleep seconds between loops when idle"),
    max_loops: Optional[int] = typer.Option(None, help="Max loops before exit (for tests)"),
):
    """Run scheduler ticks and process jobs in a simple loop."""

    queue, scheduler = easy_jobs()
    # load schedule from env JSON if provided
    schedule_from_env(scheduler)

    async def _loop():
        loops = 0
        while True:
            await scheduler.tick()
            processed = await process_one(queue, _noop_handler)
            if not processed:
                # idle
                await asyncio.sleep(poll_interval)
            if max_loops is not None:
                loops += 1
                if loops >= max_loops:
                    break

    async def _noop_handler(job):
        # Default handler does nothing; users should write their own runners
        return None

    asyncio.run(_loop())
