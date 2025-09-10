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
    init = "init"
    revision = "revision"
    upgrade = "upgrade"
    downgrade = "downgrade"
    current = "current"
    history = "history"
    stamp = "stamp"
    merge_heads = "merge-heads"
    setup_and_migrate = "setup-and-migrate"
    scaffold = "scaffold"
    scaffold_models = "scaffold-models"
    scaffold_schemas = "scaffold-schemas"


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
