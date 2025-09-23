from __future__ import annotations

from enum import Enum

from ai_infra.llm.tools.custom.cli import cli_cmd_help, cli_subcmd_help
from ai_infra.mcp.server.tools import mcp_from_functions

CLI_PROG = "svc-infra"


async def svc_infra_cmd_help() -> dict:
    """
    Get help text for svc-infra CLI.
    - Prepares project env without chdir (so we can 'cd' in the command itself).
    - Tries poetry → console script → python -m svc_infra.cli_shim.
    """
    return await cli_cmd_help(CLI_PROG)


class Subcommand(str, Enum):
    # SQL commands
    sql_init = "sql-init"
    sql_revision = "sql-revision"
    sql_upgrade = "sql-upgrade"
    sql_downgrade = "sql-downgrade"
    sql_current = "sql-current"
    sql_history = "sql-history"
    sql_stamp = "sql-stamp"
    sql_merge_heads = "sql-merge-heads"
    sql_setup_and_migrate = "sql-setup-and-migrate"
    sql_scaffold = "sql-scaffold"
    sql_scaffold_models = "sql-scaffold-models"
    sql_scaffold_schemas = "sql-scaffold-schemas"

    # Mongo commands
    mongo_prepare = "mongo-prepare"
    mongo_setup_and_prepare = "mongo-setup-and-prepare"
    mongo_ping = "mongo-ping"
    mongo_scaffold = "mongo-scaffold"
    mongo_scaffold_documents = "mongo-scaffold-documents"
    mongo_scaffold_schemas = "mongo-scaffold-schemas"
    mongo_scaffold_resources = "mongo-scaffold-resources"

    # Observability commands
    obs_up = "obs-up"
    obs_down = "obs-down"
    obs_scaffold = "obs-scaffold"


async def svc_infra_subcmd_help(subcommand: Subcommand) -> dict:
    """
    Get help text for a specific subcommand of svc-infra CLI.
    (Enum keeps a tight schema; function signature remains simple.)
    """
    return await cli_subcmd_help(CLI_PROG, subcommand)


mcp = mcp_from_functions(
    name="svc-infra-cli-mcp",
    functions=[
        svc_infra_cmd_help,
        svc_infra_subcmd_help,
    ],
)

if __name__ == "__main__":
    mcp.run(transport="stdio")
