from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import cast

from .scheduler import InMemoryScheduler

logger = logging.getLogger(__name__)


def _resolve_target(path: str) -> Callable[[], Awaitable[None]]:
    mod_name, func_name = path.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name)
    if asyncio.iscoroutinefunction(fn):
        return cast("Callable[[], Awaitable[None]]", fn)

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
        except Exception as e:
            logger.warning("Failed to load scheduled job entry %s: %s", t, e)
            continue
