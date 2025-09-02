import typer
from langgraph.graph import END, START

from ai_infra import CoreGraph
from ai_infra.graph import ConditionalEdge, Edge
from ai_infra.mcp.client.core import CoreMCPClient
from ai_infra.llm import PROVIDER

from svc_infra.cli.agent.prints import _print_exec_transcript
from .nodes import plan_with_action_planner, execute_plan, recover_from_error
from .states import CLIAgentState
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

async def agent_cmd(
        query: str = typer.Argument(..., help="Natural-language request for the agent to execute."),
        provider: str = typer.Option(
            PROVIDER,
            "--provider", "-p",
            help="LLM provider key (e.g., openai, anthropic, azure_openai)."
        ),
        model: str | None = typer.Option(
            None,
            "--model", "-m",
            help="Model name for the provider. Omit, if you want to set to the default model for the provider."
        ),
        autoapprove_tools: bool = typer.Option(
            False,
            "--autoapprove/--no-autoapprove",
            help="Auto-approve tool calls without interactive prompts."
        ),
        quiet_tools: bool = typer.Option(
            False,
            "--quiet-tools/--no-quiet-tools",
            help="Hide tool stdout/stderr in the transcript."
        ),
        max_lines: int = typer.Option(
            60,
            "--max-lines",
            help="Max lines of tool output to show per step."
        ),
        show_error_context: bool = typer.Option(
            True,
            "--show-error-context/--no-show-error-context",
            help="Show a short context excerpt when a tool fails."
        ),
        max_tool_calls: int = typer.Option(
            5,
            "--max-tool-calls",
            help="Budget for tool calls; the agent stops when exhausted."
        ),
):
    """
    Run the CLI agent with the given parameters. This function initializes the agent's state, sets up the necessary tools,
    and executes the agent's planning and execution graph. It handles user interruptions and prints the execution transcript if applicable.
    This agent has access to cli commands, project management functionalities, db management functionalities, and scaffolding auth related management for existing db setups and applications.
    """
    client = CoreMCPClient([
        {"command": "cli-mcp", "transport": "stdio"},
        {"command": "project-management-mcp", "transport": "stdio"},
        {"command": "db-management-mcp", "transport": "stdio"},
        {"command": "auth-infra-mcp", "transport": "stdio"},
    ])
    tools = await client.list_tools()

    initial: CLIAgentState = {
        "query": query,
        "provider": provider,
        "model_name": model,
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