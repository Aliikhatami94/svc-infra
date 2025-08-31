import asyncio
import os
import json

import typer
from pathlib import Path

from ai_infra.mcp.client.core import CoreMCPClient

from svc_infra.cli.ai.utils import _print_warning, _resolve_provider, _resolve_model, _print_exec_transcript, _print_numbered_plan
from svc_infra.cli.ai.context import cli_planner_sys_msg

from ai_infra.llm import CoreAgent
from .constants import (
    DANGEROUS,
    EXEC_POLICY,
)
from ai_infra.llm.agents.custom.tool_planner.main import tool_planner
from .tools import svc_infra_helper_md


client = CoreMCPClient([
    {"command": "cli-mcp", "transport": "stdio"},
    {"command": "project-management-mcp", "transport": "stdio"},
])

async def cli_agent(
        query: str = typer.Argument(..., help="e.g. 'init alembic and create migrations'"),
        autoapprove: bool = typer.Option(False, "--autoapprove", help="Auto-approve all tool calls during EXECUTION"),
        auto: bool = typer.Option(False, "--auto", help="Fully autonomous: approve plan + tool calls"),
        db_url: str = typer.Option("", "--db-url", help="Set $DATABASE_URL for tools (never printed)"),
        max_lines: int = typer.Option(60, "--max-lines", help="Max lines when printing tool output"),
        quiet_tools: bool = typer.Option(False, "--quiet-tools", help="Hide tool output; show only AI summaries"),
        plan_only: bool = typer.Option(False, "--plan-only", help="Only generate a plan; don't execute"),
        exec_only: bool = typer.Option(False, "--exec-only", help="Only execute a plan from --plan-file"),
        plan_file: str = typer.Option("", "--plan-file", help="Path to save/load the plan when using plan-only/exec-only"),
        provider: str = typer.Option("openai", "--provider", help="LLM provider (e.g. openai, anthropic, google)"),
        model: str = typer.Option("default", "--model", help="Model name key (e.g. gpt_5_mini, sonnet, gemini_1_5_pro)"),
        show_error_context: bool = typer.Option(True, "--show-error-context", help="Print partial tool output when a step fails"),
):
    # -- autonomy flags
    if auto:
        autoapprove = True

    # -- env prep
    def _is_db_action(q: str) -> bool:
        ql = (q or "").lower()
        return any(word in ql for word in ("alembic", "migrate", "migration", "init", "postgres", "psql", "database", "db"))

    if db_url:
        os.environ["DATABASE_URL"] = db_url
    elif _is_db_action(query) and not os.getenv("DATABASE_URL"):
        _print_warning("⚠️  No DATABASE_URL set. Some commands might fail.")

    # -- model selection
    prov, models_key = _resolve_provider(provider)
    model_name = _resolve_model(models_key, model)

    # -- basic arg rules
    if plan_only and exec_only:
        raise typer.BadParameter("Use only one of --plan-only or --exec-only, not both.")

    tools = await client.list_tools()

    # =========================
    # 1) PLAN via tool_planner
    # =========================
    # We keep terminal mode so the human-in-the-loop prompt lives *inside* tool_planner.
    plan_messages = [
        {"role": "system", "content": cli_planner_sys_msg()},
        {"role": "user", "content": query},
    ]
    plan_result = await tool_planner(
        messages=plan_messages,
        tools=tools,
        io_mode="terminal",  # HITL happens inside tool_planner; no duplicate prompts here
        provider=prov,
        model_name=model_name,
    )

    # Show what was proposed (or why skipped)
    presentation = plan_result.get("presentation_md") or ""
    if presentation.strip():
        _print_numbered_plan(presentation)

    # Respect planner’s decision
    if plan_result.get("aborted"):
        print("\nAborted during planning. (Nothing executed.)")
        return
    if plan_result.get("awaiting_approval"):
        print("\nAwaiting approval (planner is in API mode) — not executing.")
        return
    if not plan_result.get("approved"):
        print("\nPlan not approved. (Nothing executed.)")
        return

    # If the user only wanted the plan, save/show and exit
    if plan_only:
        if plan_file:
            Path(plan_file).write_text(json.dumps(plan_result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSaved plan to {plan_file}")
        return

    # =========================
    # 2) EXECUTE
    # =========================

    # exec-only path: load pre-saved plan_result
    if exec_only:
        if not plan_file:
            raise typer.BadParameter("--exec-only requires --plan-file")
        fpath = Path(plan_file)
        if not fpath.exists():
            raise typer.BadParameter(f"Plan file not found: {fpath}")
        try:
            plan_result = json.loads(fpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # allow old files that only had presentation text
            plan_result = {"plan": [], "presentation_md": fpath.read_text(encoding="utf-8"), "approved": True}
        # echo what we’re about to run
        pres = plan_result.get("presentation_md") or ""
        if pres.strip():
            _print_numbered_plan(pres)

    # optional final confirmation (user can skip with --yes or --auto)
    if not plan_result.get("approved"):
        print("\nPlan not approved. (Nothing executed.)")
        return

    # runtime HITL gate for *tool calls* (separate from *plan* approval inside tool_planner)
    agent = CoreAgent()

    async def hitl_gate(name: str, args: dict):
        cmd = (
                args.get("command")
                or " && ".join(args.get("commands", []) or [])
                or args.get("cmd")
                or args.get("shell")
                or ""
        )
        preview = cmd.strip() or f"{name}({json.dumps(args, separators=(',', ':'), ensure_ascii=False)})"

        if not quiet_tools:
            print(f"Executing -> {preview}")

        if any(d in preview for d in DANGEROUS):
            return {"action": "block", "replacement": "[blocked: potentially destructive]"}

        if autoapprove:
            return {"action": "pass"}

        ans = (await asyncio.to_thread(input, "Approve? [y]es / [b]lock: ")).strip().lower()
        if ans in ("b", "block"):
            return {"action": "block", "replacement": "[blocked by user]"}
        return {"action": "pass"}

    agent.set_hitl(on_tool_call_async=hitl_gate)

    # Build execution prompt. If planner skipped (no plan), just pass the goal.
    plan_steps = plan_result.get("plan") or []
    questions = plan_result.get("questions") or []

    # You can shape this however your executor works best:
    # we include the structured steps when present; otherwise include the goal.
    if plan_steps:
        exec_payload = json.dumps(plan_steps, ensure_ascii=False, indent=2)
        exec_instruction = f"Execute this structured plan now:\n{exec_payload}"
    else:
        exec_instruction = f"Goal (no plan needed): {query}\nExecute directly."

    if questions:
        exec_instruction += f"\n\nOpen questions (answer if needed before execution):\n- " + "\n- ".join(questions)

    exec_messages = [
        {"role": "system", "content": EXEC_POLICY},
        {"role": "system", "content": "You can manage the project as well as executing shell commands on a developer's local machine. Each command must run as-is. Output results using RUN/OK/FAIL markers. Be concise."},
        {"role": "system", "content": "If a DB connection is needed, prefer: `--database-url \"$DATABASE_URL\"`."},
        {"role": "human", "content": exec_instruction},
    ]

    # spacer
    print()

    exec_resp = await agent.arun_agent(
        messages=exec_messages,
        provider=prov,
        model_name=model_name,
        tools=tools,
    )

    print("\n=== EXECUTION ===")
    _print_exec_transcript(
        exec_resp,
        show_tool_output=not quiet_tools,
        max_lines=max_lines,
        quiet_tools=quiet_tools,
        show_error_context=show_error_context,
    )