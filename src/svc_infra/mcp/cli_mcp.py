from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel
from ai_infra.mcp.server.tools import mcp_from_functions

from svc_infra.db import get_database_url_from_env
from svc_infra.db.setup.core import _prepare_env

from svc_infra.mcp._runner import _run_from_root

# ---------- public tools ----------

async def svc_infra_help(database_url: Optional[str] = None) -> dict:
    """
    Get help text for svc-infra CLI.
    - Prepares project env without chdir (so we can 'cd' in the command itself).
    - Tries poetry → console script → python -m svc_infra.cli_shim.
    """
    db_url = database_url or get_database_url_from_env(required=False)
    root = _prepare_env(database_url=db_url, chdir=False)
    text = await _run_from_root(root, ["--help"])
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

# Optional Pydantic wrapper for schema-rich tool contracts
class SubcommandHelpRequest(BaseModel):
    subcommand: Subcommand
    database_url: Optional[str] = None


async def svc_infra_subcommand_help(
        subcommand: Subcommand,
        database_url: Optional[str] = None,
) -> dict:
    """
    Get help text for a specific subcommand of svc-infra CLI.
    (Enum keeps a tight schema; function signature remains simple.)
    """
    db_url = database_url or get_database_url_from_env(required=False)
    root = _prepare_env(database_url=db_url, chdir=False)

    cmd = subcommand.value
    text = await _run_from_root(root, [cmd, "--help"])
    return {
        "ok": True,
        "action": "subcommand_help",
        "subcommand": cmd,
        "project_root": str(root),
        "help": text,
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

# async def main():
#     r = await svc_infra_help()
#     return r
#
# if __name__ == '__main__':
#     import asyncio
#     r = asyncio.run(main())
#     print(r)