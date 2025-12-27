"""MCP (Model Context Protocol) server for svc-infra CLI.

This module provides an MCP server that exposes svc-infra CLI commands as tools
for AI assistants and agents.

Available Tools:
    - svc_infra_cmd_help: Get help text for the svc-infra CLI
    - svc_infra_subcmd_help: Get help for specific subcommands
    - svc_infra_docs_help: Get documentation help

Example:
    # Run the MCP server
    python -m svc_infra.mcp.svc_infra_mcp

    # Or use programmatically
    from svc_infra.mcp import mcp, Subcommand, svc_infra_subcmd_help

    # Get help for a subcommand
    result = await svc_infra_subcmd_help(Subcommand.sql_upgrade)

See Also:
    - ai-infra MCP documentation for client usage
    - svc-infra CLI reference for available commands

Note:
    This module requires ai-infra to be installed. If ai-infra is not available,
    imports will raise ImportError with a helpful message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .svc_infra_mcp import (
        CLI_PROG as CLI_PROG,
    )
    from .svc_infra_mcp import (
        Subcommand as Subcommand,
    )
    from .svc_infra_mcp import (
        mcp as mcp,
    )
    from .svc_infra_mcp import (
        svc_infra_cmd_help as svc_infra_cmd_help,
    )
    from .svc_infra_mcp import (
        svc_infra_docs_help as svc_infra_docs_help,
    )
    from .svc_infra_mcp import (
        svc_infra_subcmd_help as svc_infra_subcmd_help,
    )

__all__ = [
    # MCP server instance
    "mcp",
    # Subcommand enum
    "Subcommand",
    # Tool functions
    "svc_infra_cmd_help",
    "svc_infra_subcmd_help",
    "svc_infra_docs_help",
    # Constants
    "CLI_PROG",
]


def __getattr__(name: str):
    """Lazy import to defer ai-infra dependency until runtime."""
    if name in __all__:
        try:
            from . import svc_infra_mcp

            return getattr(svc_infra_mcp, name)
        except ImportError as e:
            if "ai_infra" in str(e):
                raise ImportError(
                    f"Cannot import '{name}' from svc_infra.mcp: "
                    "ai-infra package is required. Install with: pip install ai-infra"
                ) from e
            raise
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
