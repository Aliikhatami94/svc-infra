from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path


async def run_fixtures(
    loaders: Iterable[Callable[[], None | Awaitable[None]]],
    *,
    run_once_file: str | None = None,
) -> None:
    """Run a sequence of fixture loaders (sync or async).

    - If run_once_file is provided and exists, does nothing.
    - On success, creates the run_once_file sentinel (parent dirs included).
    """
    if run_once_file:
        sentinel = Path(run_once_file)
        if sentinel.exists():
            return
    for fn in loaders:
        res = fn()
        if inspect.isawaitable(res):
            await res
    if run_once_file:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        Path(run_once_file).write_text("ok")


def make_on_load_fixtures(
    *loaders: Callable[[], None | Awaitable[None]], run_once_file: str | None = None
) -> Callable[[], Awaitable[None]]:
    """Return an async callable suitable for add_data_lifecycle(on_load_fixtures=...)."""

    async def _runner() -> None:
        await run_fixtures(loaders, run_once_file=run_once_file)

    return _runner


__all__ = ["run_fixtures", "make_on_load_fixtures"]
