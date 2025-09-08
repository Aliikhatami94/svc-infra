from __future__ import annotations

from enum import Enum

from ai_infra.mcp.server.tools import mcp_from_functions

CLI_PROG = "svc-infra"

def _get_helpers():
    # Try new helpers; fall back to local runner if missing
    try:
        from ai_infra.llm.tools.custom.cli import cli_cmd_help, cli_subcmd_help  # type: ignore[attr-defined]
        return cli_cmd_help, cli_subcmd_help
    except Exception:
        from pathlib import Path
        from svc_infra.app.root import resolve_project_root
        from svc_infra.cli._bootstrap import find_env_file, load_env_if_present
        from svc_infra.mcp._runner import _run_from_root

        async def _cmd_help(_prog: str) -> dict:
            root = resolve_project_root()
            env = find_env_file(start=Path(root))
            load_env_if_present(env, override=False)
            text = await _run_from_root(Path(root), ["--help"])
            return {"ok": True, "action": "help", "project_root": str(root), "help": text}

        async def _subcmd_help(_prog: str, subcmd: "Subcommand | str") -> dict:
            root = resolve_project_root()
            env = find_env_file(start=Path(root))
            load_env_if_present(env, override=False)
            cmd = subcmd.value if hasattr(subcmd, "value") else str(subcmd)
            text = await _run_from_root(Path(root), [cmd, "--help"])
            return {"ok": True, "action": "subcommand_help", "subcommand": cmd, "project_root": str(root), "help": text}

        return _cmd_help, _subcmd_help

cli_cmd_help, cli_subcmd_help = _get_helpers()

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