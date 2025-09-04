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
    ])

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()