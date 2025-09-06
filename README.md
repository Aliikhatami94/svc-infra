# svc-infra

Infrastructure for building and deploying prod-ready applications:
- **FastAPI** app scaffolding with versioned mounting and uniform error handling
- **SQLAlchemy** async DB integration + Alembic CLI
- **Auth** via fastapi-users (session/refresh/OAuth)
- Simple **CRUD** router generator
- Logging, metrics, tracing, health checks

## Install

```bash
poetry add svc-infra
# or
pip install svc-infra
```

## MCP stdio CLIs

Two MCP servers are available as Node shims that launch the Python modules via uvx:
- auth-infra-mcp -> svc_infra.auth.mcp
- db-management-mcp -> svc_infra.db.setup.mcp

Prerequisites:
- Python 3.11+ available to uvx
- uv (uvx) installed and on PATH (for macOS: `brew install uv`)

Run locally from this repo:
- ./mcp-shim/bin/auth-infra-mcp.js
- ./mcp-shim/bin/db-infra-mcp.js

Notes:
- The shims default to repo https://github.com/Aliikhatami94/svc-infra.git at ref "main". Override with env vars:
  - SVC_INFRA_REPO: Git URL (e.g., your fork)
  - SVC_INFRA_REF: Branch, tag, or commit
  - UVX_REFRESH: Set to force uvx to refresh the environment
- You can also run via npm scripts: `npm run auth-mcp` or `npm run db-mcp` after installing Node 18+.

## MCP server config examples

Add entries like these to your Copilot MCP config (e.g., ~/.config/github-copilot/intellij/mcp.json):

```json
{
  "servers": {
    "auth-infra-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "--package=github:Aliikhatami94/svc-infra",
        "auth-infra-mcp"
      ]
    },
    "db-management-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "--package=github:Aliikhatami94/svc-infra",
        "db-management-mcp"
      ]
    }
  }
}
```

Tip:
- If you want to pin a specific ref (branch, tag, commit), set SVC_INFRA_REF in your environment before launching the IDE.
