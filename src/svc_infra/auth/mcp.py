from ai_infra import mcp_from_functions

from .scaffold import (
    scaffold_auth_core,
    scaffold_auth_models_core,
    scaffold_auth_schemas_core,
)

mcp = mcp_from_functions(
    name="auth-infra-mcp",
    functions=[
        scaffold_auth_core,
        scaffold_auth_models_core,
        scaffold_auth_schemas_core,
    ])

def main():
    mcp.run(transport="stdio")

if __name__ == '__main__':
    main()