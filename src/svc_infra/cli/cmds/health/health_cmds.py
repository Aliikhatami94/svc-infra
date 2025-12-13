"""Health check CLI commands module.

Re-exports from health/__init__.py for backward compatibility.
"""

from svc_infra.cli.cmds.health import register

__all__ = ["register"]
