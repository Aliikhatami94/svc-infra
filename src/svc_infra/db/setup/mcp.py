from __future__ import annotations

import sys
from pathlib import Path
from ai_infra import mcp_from_functions

from .core import (
    init_alembic,
    revision,
    upgrade,
    downgrade,
    current,
    history,
    stamp,
    merge_heads,
)
from .scaffold import (
    scaffold_core,
    scaffold_models_core,
    scaffold_schemas_core,
)

from .utils import build_alembic_config, _is_mod_available
from .core import _prepare_env

def preflight(project_root: str, database_url: str | None = None) -> dict:
    """Check environment and dependencies for database migrations."""
    root = _prepare_env(project_root, database_url=database_url)
    info = {
        "cwd": str(Path.cwd()),
        "project_root": str(root),
        "py_version": sys.version,
        "drivers": {
            "psycopg": _is_mod_available("psycopg"),
            "psycopg2": _is_mod_available("psycopg2"),
            "asyncpg": _is_mod_available("asyncpg"),
        },
    }
    try:
        cfg = build_alembic_config(root)
        info["script_location"] = cfg.get_main_option("script_location")
        info["effective_sqlalchemy_url"] = cfg.get_main_option("sqlalchemy.url")
    except Exception as e:
        return {"ok": False, "error": str(e), "preflight": info}
    return {"ok": True, "preflight": info}

mcp = mcp_from_functions(
    name="db-infra-mcp",
    functions=[
        preflight,
        # High-level
        init_alembic,
        revision,
        upgrade,
        downgrade,
        current,
        history,
        stamp,
        merge_heads,
        # Scaffolding
        scaffold_core,
        scaffold_models_core,
        scaffold_schemas_core,
    ])

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()