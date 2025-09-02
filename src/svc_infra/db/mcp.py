from ai_infra import mcp_from_functions

from .core import (
    db_init_core,
    db_revision_core,
    db_upgrade_core,
    db_downgrade_core,
    db_current_core,
    db_history_core,
    db_stamp_core,
    db_drop_table_core,
    db_merge_heads_core,
)

mcp = mcp_from_functions(
    name="db-management",
    functions=[
        db_init_core,
        db_revision_core,
        db_upgrade_core,
        db_downgrade_core,
        db_current_core,
        db_history_core,
        db_stamp_core,
        db_drop_table_core,
        db_merge_heads_core,
])

def main():
    mcp.run(transport="stdio")