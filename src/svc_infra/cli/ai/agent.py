import asyncio
import os
import json

import typer
from pathlib import Path

from ai_infra.mcp.client.core import CoreMCPClient

from svc_infra.cli.ai.utils import _print_warning, _resolve_provider, _resolve_model, _print_exec_transcript, _print_numbered_plan
from svc_infra.cli.ai.context import cli_agent_sys_msg

from ai_infra.llm import CoreLLM, CoreAgent
from .constants import (
    DANGEROUS,
    EXEC_POLICY,
)


client = CoreMCPClient([
    {
        "command": "cli",
        "transport": "stdio",
    },
    {
        "command": "project-management-mcp",
        "transport": "stdio",
    },
])

# --- Super-compact, low-token policies --- #

async def agent(
        query: str = typer.Argument(..., help="e.g. 'init alembic and create migrations'"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm plan execution"),
        autoapprove: bool = typer.Option(False, "--autoapprove", help="Auto-approve all tool calls"),
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
    if auto:
        autoapprove = True
        yes = True

    def _is_db_action(q: str) -> bool:
        ql = (q or "").lower()
        return any(word in ql for word in ("alembic", "migrate", "migration", "init", "postgres", "psql", "database", "db"))

    # Set DB URL in env if provided; warn only if likely DB-related
    if db_url:
        os.environ["DATABASE_URL"] = db_url
    elif _is_db_action(query) and not os.getenv("DATABASE_URL"):
        _print_warning("⚠️  No DATABASE_URL set. Some commands might fail.")

    # Provider & model setup
    prov, models_key = _resolve_provider(provider)
    model_name = _resolve_model(models_key, model)
    llm = CoreLLM()
    agent = CoreAgent()

    # Branching flags validation
    if plan_only and exec_only:
        raise typer.BadParameter("Use only one of --plan-only or --exec-only, not both.")

    # -------- PLAN -------- (unless exec-only)
    plan_text = ""
    if exec_only:
        # Load plan from file
        if not plan_file:
            raise typer.BadParameter("--exec-only requires --plan-file")
        fpath = Path(plan_file)
        if not fpath.exists():
            raise typer.BadParameter(f"Plan file not found: {fpath}")
        plan_text = fpath.read_text(encoding="utf-8")
        # Print consistently formatted plan
        _print_numbered_plan(plan_text)
    else:
        plan_text = llm.chat(
            user_msg=query,
            system=cli_agent_sys_msg(),
            provider=prov,
            model_name=model_name,
        ).content or ""

        if not plan_text:
            print("AI (PLAN): No plan was generated.")
            return

        # Print consistently formatted plan
        _print_numbered_plan(plan_text)

        if plan_only:
            if plan_file:
                Path(plan_file).write_text(plan_text, encoding="utf-8")
                print(f"\nSaved plan to {plan_file}")
            return

        if not yes:
            proceed = input("\nProceed with execution? [y/N]: ").strip().lower()
            if proceed not in ("y", "yes"):
                print("Aborted. (Nothing executed.)")
                return

    # -------- EXECUTE --------

    async def hitl_gate(name: str, args: dict):
        # try common keys first
        cmd = (
            args.get("command") or
            " && ".join(args.get("commands", []) or []) or
            args.get("cmd") or
            args.get("shell") or
            ""
        )

        # redact here if you have a _redact() util
        preview = cmd.strip() or f"{name}({json.dumps(args, separators=(',', ':'), ensure_ascii=False)})"

        if not quiet_tools:
            print(f"Executing -> {preview}")

        # dangerous-check should consider the final preview string
        if any(d in preview for d in DANGEROUS):
            return {"action": "block", "replacement": "[blocked: potentially destructive]"}

        if autoapprove:
            return {"action": "pass"}

        ans = (await asyncio.to_thread(input, "Approve? [y]es / [b]lock: ")).strip().lower()
        if ans in ("b", "block"):
            return {"action": "block", "replacement": "[blocked by user]"}
        return {"action": "pass"}

    agent.set_hitl(on_tool_call_async=hitl_gate)

    exec_messages = [
        {"role": "system", "content": EXEC_POLICY},
        {"role": "system", "content": "You can manage the project as well as executing shell commands on a developer's local machine. Each command must run as-is. Output results using RUN/OK/FAIL markers. Be concise."},
        {"role": "system", "content": "If a DB connection is needed, prefer: `--database-url \"$DATABASE_URL\"`."},
        {"role": "human", "content": f"Execute this plan now:\n{query}"},
    ]

    # Visual spacer between the Plan and the upcoming "Executing ->" lines
    print()

    tools = await client.list_tools()
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