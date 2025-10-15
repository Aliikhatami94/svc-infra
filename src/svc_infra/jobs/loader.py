from __future__ import annotations

import asyncio
import importlib
import json
import os
from typing import Awaitable, Callable

from .scheduler import InMemoryScheduler


def _resolve_target(path: str) -> Callable[[], Awaitable[None]]:
    mod_name, func_name = path.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name)
    if asyncio.iscoroutinefunction(fn):
        return fn  # type: ignore[return-value]

    # wrap sync into async
    async def _wrapped():
        fn()

    return _wrapped


def schedule_from_env(scheduler: InMemoryScheduler, env_var: str = "JOBS_SCHEDULE_JSON") -> None:
    data = os.getenv(env_var)
    if not data:
        return
    try:
        tasks = json.loads(data)
    except json.JSONDecodeError:
        return
    if not isinstance(tasks, list):
        return
    for t in tasks:
        try:
            name = t["name"]
            interval = int(t.get("interval_seconds", 60))
            target = t["target"]
            fn = _resolve_target(target)
            scheduler.add_task(name, interval, fn)
        except Exception:
            # ignore bad entries
            continue
