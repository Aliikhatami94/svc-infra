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
    setup_and_migrate,
)
from .scaffold import (
    scaffold_core,
    scaffold_models_core,
    scaffold_schemas_core,
)

mcp = mcp_from_functions(
    name="db-infra-mcp",
    functions=[
        # High-level
        init_alembic,
        revision,
        upgrade,
        downgrade,
        current,
        history,
        stamp,
        merge_heads,
        setup_and_migrate,
        # Scaffolding
        scaffold_core,
        scaffold_models_core,
        scaffold_schemas_core,
    ])

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()