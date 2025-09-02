from langgraph.graph import END, START

from ai_infra import CoreGraph
from ai_infra.graph import ConditionalEdge, Edge
from ai_infra.mcp.client.core import CoreMCPClient
from ai_infra.llm import PROVIDER, MODEL

from svc_infra.cli.ai.utils import _print_exec_transcript
from .nodes import plan_with_action_planner, execute_plan, recover_from_error
from .states import CLIAgentState
from ..utils import (
    _resolve_provider,
    _resolve_model,
)
from .utils import (_on_exit, _on_enter)


MAX_RETRIES = 2

CLIAgentGraph = CoreGraph(
    state_type=CLIAgentState,
    node_definitions=[
        plan_with_action_planner,
        execute_plan,
        recover_from_error
    ],
    edges=[
        Edge(start=START, end="plan_with_action_planner"),
        ConditionalEdge(
            start="plan_with_action_planner",
            router_fn=lambda s: (
                END
                if (bool(s.get("aborted"))
                    or not bool(s.get("approved"))
                    or bool(s.get("awaiting_approval")))
                else "execute_plan"
            ),
            targets=["execute_plan", END],
        ),
        ConditionalEdge(
            start="execute_plan",
            router_fn=lambda s: (
                END if (bool(s.get("hard_stop")))
                else ("recover_from_error" if (bool(s.get("had_error")) and int(s.get("retry_count") or 0) < MAX_RETRIES) else END)
            ),
            targets=["recover_from_error", END],
        ),
        Edge(start="recover_from_error", end="execute_plan"),
    ],
)

async def run_cli(
        *,
        query: str,
        provider_key: str = PROVIDER,
        model_key: str = MODEL,
        autoapprove_tools: bool = False,
        quiet_tools: bool = False,
        max_lines: int = 60,
        show_error_context: bool = True,
        max_tool_calls: int = 5
):
    # resolve provider/model
    prov, models_key = _resolve_provider(provider_key)
    model_name = _resolve_model(models_key, model_key)

    # shared MCP tools
    client = CoreMCPClient([
        {"command": "cli-mcp", "transport": "stdio"},
        {"command": "project-management-mcp", "transport": "stdio"},
        {"command": "db-management-mcp", "transport": "stdio"},
        {"command": "auth-infra-mcp", "transport": "stdio"},
    ])
    tools = await client.list_tools()

    initial: CLIAgentState = {
        "query": query,
        "provider": prov,
        "model_name": model_name,
        "tools": tools,
        "autoapprove_tools": autoapprove_tools,
        "quiet_tools": quiet_tools,
        "max_lines": max_lines,
        "show_error_context": show_error_context,
        "max_tool_calls": max_tool_calls,
        "tool_calls_used": 0,
    }

    try:
        result: CLIAgentState = await CLIAgentGraph.arun(
            initial,
            on_enter=_on_enter,
            on_exit=_on_exit,
            trace=None,
            config={"recursion_limit": 10},
        )
    except KeyboardInterrupt:
        print("\n^C caught — aborting.")
        return

    # If planner ended without approval (either aborted or awaiting human), stop here.
    if not result.get("approved"):
        print("\nPlan not approved. (Nothing executed.)")
        if result.get("presentation_md"):
            print("\n" + result["presentation_md"])
        return

    # If we executed, print transcript like before
    if "exec_response" in result:
        print("\n=== EXECUTION ===")
        _print_exec_transcript(
            result["exec_response"],
            show_tool_output=not quiet_tools,
            max_lines=max_lines,
            quiet_tools=quiet_tools,
            show_error_context=show_error_context,
        )