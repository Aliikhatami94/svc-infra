from __future__ import annotations

from enum import Enum

from ai_infra.llm.tools.custom.cli import cli_cmd_help, cli_subcmd_help
from ai_infra.mcp.server.tools import mcp_from_functions

from svc_infra.app.env import prepare_env
from svc_infra.cli.foundation.runner import run_from_root

CLI_PROG = "svc-infra"


async def svc_infra_cmd_help() -> dict:
    """
    Get help text for svc-infra CLI.
    - Prepares project env without chdir (so we can 'cd' in the command itself).
    - Tries poetry → console script → python -m svc_infra.cli_shim.
    """
    return await cli_cmd_help(CLI_PROG)


# No dedicated 'docs list' function — users can use 'docs --help' to discover topics.


async def svc_infra_docs_help() -> dict:
    """
    Run 'svc-infra docs --help' and return its output.
    Prepares the project environment and executes from the repo root so
    environment-provided docs directories and local topics are discoverable.
    """
    root = prepare_env()
    text = await run_from_root(root, CLI_PROG, ["docs", "--help"])
    return {
        "ok": True,
        "action": "docs_help",
        "project_root": str(root),
        "help": text,
    }


class Subcommand(str, Enum):
    # SQL group commands
    sql_init = "sql init"
    sql_revision = "sql revision"
    sql_upgrade = "sql upgrade"
    sql_downgrade = "sql downgrade"
    sql_current = "sql current"
    sql_history = "sql history"
    sql_stamp = "sql stamp"
    sql_merge_heads = "sql merge-heads"
    sql_setup_and_migrate = "sql setup-and-migrate"
    sql_scaffold = "sql scaffold"
    sql_scaffold_models = "sql scaffold-models"
    sql_scaffold_schemas = "sql scaffold-schemas"
    sql_export_tenant = "sql export-tenant"
    sql_seed = "sql seed"

    # Mongo group commands
    mongo_prepare = "mongo prepare"
    mongo_setup_and_prepare = "mongo setup-and-prepare"
    mongo_ping = "mongo ping"
    mongo_scaffold = "mongo scaffold"
    mongo_scaffold_documents = "mongo scaffold-documents"
    mongo_scaffold_schemas = "mongo scaffold-schemas"
    mongo_scaffold_resources = "mongo scaffold-resources"

    # Observability group commands
    obs_up = "obs up"
    obs_down = "obs down"
    obs_scaffold = "obs scaffold"

    # Docs group
    docs_help = "docs --help"
    docs_show = "docs show"

    # DX group
    dx_openapi = "dx openapi"
    dx_migrations = "dx migrations"
    dx_changelog = "dx changelog"
    dx_ci = "dx ci"

    # Jobs group
    jobs_run = "jobs run"

    # SDK group
    sdk_ts = "sdk ts"
    sdk_py = "sdk py"
    sdk_postman = "sdk postman"


async def svc_infra_subcmd_help(subcommand: Subcommand) -> dict:
    """
    Get help text for a specific subcommand of svc-infra CLI.
    (Enum keeps a tight schema; function signature remains simple.)
    """
    tokens = subcommand.value.split()
    if len(tokens) == 1:
        return await cli_subcmd_help(CLI_PROG, subcommand)

    root = prepare_env()
    text = await run_from_root(root, CLI_PROG, [*tokens, "--help"])
    return {
        "ok": True,
        "action": "subcommand_help",
        "subcommand": subcommand.value,
        "project_root": str(root),
        "help": text,
    }


mcp = mcp_from_functions(
    name="svc-infra-cli-mcp",
    functions=[
        svc_infra_cmd_help,
        svc_infra_subcmd_help,
        svc_infra_docs_help,
        # Docs listing is available via 'docs --help'; no separate MCP function needed.
    ],
)


if __name__ == "__main__":
    mcp.run(transport="stdio")
