from __future__ import annotations

import inspect
from typing import Callable, Iterable, Optional

from fastapi import FastAPI

from svc_infra.cli.cmds.db.sql.alembic_cmds import cmd_setup_and_migrate


def add_data_lifecycle(
    app: FastAPI,
    *,
    auto_migrate: bool = True,
    database_url: str | None = None,
    discover_packages: Optional[list[str]] = None,
    with_payments: bool | None = None,
    on_load_fixtures: Optional[Callable[[], None]] = None,
    retention_jobs: Optional[Iterable[Callable[[], None]]] = None,
    erasure_job: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Wire data lifecycle conveniences:

    - auto_migrate: run end-to-end Alembic setup-and-migrate on startup (idempotent).
    - on_load_fixtures: optional callback to load reference/fixture data once at startup.
    - retention_jobs: optional list of callables to register purge tasks (scheduler integration is external).
    - erasure_job: optional callable to trigger a GDPR erasure workflow for a given principal ID.

    This helper is intentionally minimal: it coordinates existing building blocks
    and offers extension points. Jobs should be scheduled using svc_infra.jobs helpers.
    """

    async def _run_lifecycle() -> None:
        # Startup
        if auto_migrate:
            cmd_setup_and_migrate(
                database_url=database_url,
                overwrite_scaffold=False,
                create_db_if_missing=True,
                create_followup_revision=True,
                initial_message="initial schema",
                followup_message="autogen",
                discover_packages=discover_packages,
                with_payments=with_payments,
            )
        if on_load_fixtures:
            res = on_load_fixtures()
            if inspect.isawaitable(res):
                await res  # type: ignore[misc]

    app.add_event_handler("startup", _run_lifecycle)

    # Store optional jobs on app.state for external schedulers to discover/register.
    if retention_jobs is not None:
        app.state.data_retention_jobs = list(retention_jobs)
    if erasure_job is not None:
        app.state.data_erasure_job = erasure_job


__all__ = ["add_data_lifecycle"]
