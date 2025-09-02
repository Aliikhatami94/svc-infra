from .helper import (
    _build_inventory,
    _render_json,
    _render_md,
)

async def svc_infra_helper_json(max_depth: int = 3) -> str:
    """Render a JSON inventory of the svc-infra CLI commands and options, up to max_depth levels deep."""
    try:
        inv = _build_inventory(max_depth=max_depth)
        return _render_json(inv)
    except Exception:
        return ""

async def svc_infra_helper_md(max_depth: int = 3) -> str:
    """Render a markdown inventory of the svc-infra CLI commands and options, up to max_depth levels deep."""
    try:
        # _render_md renders from live click tree; we still build/prune to bound work,
        # but we don't need inv to render; keeping symmetry with json.
        _ = _build_inventory(max_depth=max_depth)
        return _render_md(_)
    except Exception:
        return ""

from langchain_core.tools import StructuredTool

svc_infra_helper = StructuredTool.from_function(func=svc_infra_helper_json)