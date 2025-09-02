from ai_infra.llm import tools_from_functions

from .helper import (
    _build_inventory,
    _render_json,
)

async def svc_infra_helper_json(max_depth: int = 3) -> str:
    """
    Returns a JSON representation of the current service infrastructure inventory. This includes services, their configurations, dependencies, and statuses. The depth of the inventory can be controlled with the `max_depth` parameter.
    """
    try:
        inv = _build_inventory(max_depth=max_depth)
        return _render_json(inv)
    except Exception:
        return ""


svc_infra_tools = tools_from_functions(functions=[svc_infra_helper_json])