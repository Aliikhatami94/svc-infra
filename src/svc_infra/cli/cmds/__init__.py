from __future__ import annotations

from typing import Any

import typer

try:
    from svc_infra.cli.cmds.db.nosql.mongo.mongo_cmds import register as register_mongo
except ModuleNotFoundError as exc:
    _mongo_import_error = exc

    def register_mongo(app: typer.Typer) -> None:  # type: ignore[no-redef]
        def _unavailable() -> Any:
            raise ModuleNotFoundError(
                "MongoDB CLI commands require optional dependencies. Install pymongo and motor "
                "to enable `svc-infra mongo ...` commands."
            ) from _mongo_import_error

        # Provide a single helpful command instead of failing CLI import.
        app.command("unavailable")(_unavailable)


from svc_infra.cli.cmds.db.nosql.mongo.mongo_scaffold_cmds import (
    register as register_mongo_scaffold,
)
from svc_infra.cli.cmds.db.ops_cmds import register as register_db_ops
from svc_infra.cli.cmds.db.sql.alembic_cmds import register as register_alembic
from svc_infra.cli.cmds.db.sql.sql_export_cmds import register as register_sql_export
from svc_infra.cli.cmds.db.sql.sql_scaffold_cmds import (
    register as register_sql_scaffold,
)
from svc_infra.cli.cmds.docs.docs_cmds import register as register_docs
from svc_infra.cli.cmds.dx import register_dx
from svc_infra.cli.cmds.health.health_cmds import register as register_health
from svc_infra.cli.cmds.jobs.jobs_cmds import app as jobs_app
from svc_infra.cli.cmds.obs.obs_cmds import register as register_obs
from svc_infra.cli.cmds.sdk.sdk_cmds import register as register_sdk

from .help import _HELP

__all__ = [
    "register_alembic",
    "register_sql_scaffold",
    "register_sql_export",
    "register_mongo",
    "register_mongo_scaffold",
    "register_db_ops",
    "register_obs",
    "jobs_app",
    "register_sdk",
    "register_dx",
    "register_docs",
    "register_health",
    "_HELP",
]
