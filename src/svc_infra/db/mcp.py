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

mcp = mcp_from_functions(
    name="db-management-mcp",
    functions=[
        init_alembic,
        revision,
        upgrade,
        downgrade,
        current,
        history,
        stamp,
        merge_heads,
        setup_and_migrate
    ])

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()