from __future__ import annotations

from pathlib import Path
from typing import Optional
from enum import Enum

from ai_infra.mcp.server.tools import mcp_from_functions
from ai_infra.llm.tools.custom import run_cli

from svc_infra.db import get_database_url_from_env
from svc_infra.db.setup.core import _prepare_env

async def svc_infra_help(
        project_root: Path | str = ".",
        database_url: Optional[str] = None,
) -> dict:
    """Get help text for svc-infra CLI for many functionalities such as database managements, models and schema scaffolding, and more."""
    db_url = database_url or get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=db_url)
    text = await run_cli(f"cd {root} && poetry run svc-infra --help")
    return {"ok": True, "action": "help", "project_root": str(root), "help": text}


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


async def svc_infra_subcommand_help(
        subcommand: Subcommand,
        project_root: Path | str = ".",
        database_url: Optional[str] = None,
) -> dict:
    """Get help text for a specific subcommand of svc-infra CLI to learn how to use each functionality."""
    db_url = database_url or get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=db_url)

    cmd = subcommand.value
    help_text = await run_cli(f"cd {root} && poetry run svc-infra {cmd} --help")
    return {
        "ok": True,
        "action": "subcommand_help",
        "subcommand": cmd,
        "project_root": str(root),
        "help": help_text,
    }


mcp = mcp_from_functions(
    name="svc-infra-cli-mcp",
    functions=[
        svc_infra_help,
        svc_infra_subcommand_help,
    ],
)

if __name__ == "__main__":
    mcp.run(transport="stdio")