from ai_infra import mcp_from_functions

from .core import (
    scaffold_auth_core,
    scaffold_auth_models_core,
    scaffold_auth_schemas_core,
)

mcp = mcp_from_functions(
    name="auth-infra",
    functions=[
        scaffold_auth_core,
        scaffold_auth_models_core,
        scaffold_auth_schemas_core,
    ])

def main():
    mcp.run(transport="stdio")