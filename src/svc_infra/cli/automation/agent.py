import os
import sys
import typer
from pathlib import Path

from .utils import _print_warning, _resolve_provider, _resolve_model, _print_exec_transcript, _redact, _print_numbered_plan, _cli_context

from ai_infra.llm import CoreLLM, CoreAgent
from ai_infra.llm.tools.custom.terminal import run_command


# --- Super-compact, low-token policies --- #

PLAN_POLICY = (
    "ROLE=db-cli\n"
    "TASK=PLAN\n"
    "Output ONLY a short, numbered list of exact shell commands. Do not execute. No notes.\n"
    "Prefer 'svc-infra db init --database-url \"$DATABASE_URL\"' without --discover-packages."
)

EXEC_POLICY = (
    "ROLE=db-cli\n"
    "TASK=EXEC\n"
    "Loop: print 'RUN: <command>'; call terminal tool with RAW command; then print 'OK' or 'FAIL: <reason>'. "
    "Never echo secrets. One-shot. Optional final 'NEXT:' with 1–3 bullets. "
    "You may SKIP unsafe commands (e.g., unresolved placeholders or exposed credentials) and MUST explain why."
)

def agent(
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
    """
    AI-powered DB assistant (stateless, one-shot).

    Modes:
      - default: PLAN → confirm → EXECUTE (manual HITL per tool)
      - --autoapprove: PLAN → confirm → EXECUTE (autoapprove tools)
      - --auto: PLAN → autoapprove → EXECUTE (autoapprove tools)
    """
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
        # Build cross-platform hints
        os_hint = ""

        if sys.platform.startswith("darwin"):
            os_hint = (
                "You're on macOS. Use standard Unix tools. Prefer user-mode tools. Avoid sudo where possible.\n"
            )
        elif sys.platform.startswith("win"):
            os_hint = (
                "You're on Windows. Prefer PowerShell-compatible commands. Avoid Unix-only tools like grep, dirname, or bash syntax like $PWD.\n"
            )
        elif sys.platform.startswith("linux"):
            os_hint = "You're on Linux. Standard bash tools and user-space postgres are available.\n"
        plan_prompt = f"{_cli_context()}\n\n{os_hint}{PLAN_POLICY}"
        plan_text = llm.chat(
            user_msg=query,
            system=plan_prompt,
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

    def hitl_gate(tool_name: str, args: dict):
        # Prefer showing the actual command being executed (redacted)
        cmd = _redact(str((args or {}).get("command", "")))
        if autoapprove:
            if not quiet_tools:
                print(f"Executing -> {cmd}")
            return {"action": "call"}

        if not quiet_tools:
            print(f"Executing -> {cmd}")
        ok = input("Approve? [y]es / [b]lock: ").strip().lower()
        if ok in ("y", "yes"):
            return {"action": "call"}
        return {"action": "block", "replacement": "[blocked by user]"}

    agent.set_hitl(on_tool_call=hitl_gate)

    exec_messages = [
        {"role": "system", "content": EXEC_POLICY},
        {"role": "system", "content": "You are executing shell commands on a developer's local machine. Each command must run as-is. Output results using RUN/OK/FAIL markers. Be concise."},
        {"role": "system", "content": "If a DB connection is needed, prefer: `--database-url \"$DATABASE_URL\"`."},
        {"role": "human", "content": f"Execute this plan now:\n{plan_text}"},
    ]

    # Visual spacer between the Plan and the upcoming "Executing ->" lines
    print()

    exec_resp = agent.run_agent(
        messages=exec_messages,
        provider=prov,
        model_name=model_name,
        tools=[run_command],
    )

    print("\n=== EXECUTION ===")
    _print_exec_transcript(
        exec_resp,
        show_tool_output=not quiet_tools,
        max_lines=max_lines,
        quiet_tools=quiet_tools,
        show_error_context=show_error_context,
    )
