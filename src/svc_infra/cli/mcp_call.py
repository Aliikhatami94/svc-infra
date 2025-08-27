import asyncio

from ai_infra.mcp.client.core import CoreMCPClient

client = CoreMCPClient([
    {
        "command": "project-management-mcp",
        "args": [],
        "transport": "stdio",
    },
])

async def main():
    tools = await client.list_tools()
    return tools

if __name__ == '__main__':
    res = asyncio.run(main())
    print(res)
