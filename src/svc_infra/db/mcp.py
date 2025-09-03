from ai_infra import mcp_from_functions

mcp = mcp_from_functions(
    name="db-management",
    functions=[])

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()