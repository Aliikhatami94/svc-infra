from svc_infra.cli.cmds.db.sql.alembic_cmds import register as register_alembic
from svc_infra.cli.cmds.db.sql.sql_scaffold_cmds import register as register_sql_scaffold

from .help import _HELP
from .obs_cmds import register as register_obs

__all__ = [
    "register_alembic",
    "register_sql_scaffold",
    "register_obs",
    "_HELP",
]
