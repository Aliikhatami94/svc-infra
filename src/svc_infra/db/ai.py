from __future__ import annotations

from pathlib import Path
import typer
from ai_infra import Providers, Models
from ai_infra.llm import CoreAgent
from ai_infra.llm.tools.custom.terminal import run_command


def _read_readme() -> str:
    p = Path(__file__).parent / "README.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""

PLAN_POLICY = (
    "You operate the `svc-infra-db` CLI.\n"
    "Produce ONLY a short, numbered PLAN of exact shell commands you WILL run.\n"
    "Do NOT execute anything. Do NOT simulate execution. No extra notes."
)

EXEC_POLICY = (
    "You operate the `svc-infra-db` CLI.\n"
    "You will now EXECUTE the provided plan using the terminal tool:\n"
    "- Before each command, print: RUN: <command>\n"
    "- After each tool call, print: OK  (or)  FAIL: <reason>\n"
    "Keep output concise. Never print secrets."
)


def _norm_role(role: str) -> str:
    r = (role or "").lower()
    if r == "assistant":
        return "ai"
    return r


def _messages_from(resp) -> list:
    if isinstance(resp, dict) and isinstance(resp.get("messages"), list):
        return resp["messages"]
    msgs = getattr(resp, "messages", None)
    if isinstance(msgs, list):
        return msgs
    content = getattr(resp, "content", None) or (resp.get("content") if isinstance(resp, dict) else None)
    return [{"role": "ai", "content": content}] if content else []


def _get_content(m) -> str:
    if isinstance(m, dict):
        return (m.get("content") or "") if m.get("content") is not None else ""
    return getattr(m, "content", "") or ""


def _get_role(m) -> str:
    if isinstance(m, dict):
        return _norm_role(m.get("role") or m.get("type") or "")
    return _norm_role(getattr(m, "role", None) or getattr(m, "type", None) or "")


def _first_ai_text(resp) -> str:
    for m in _messages_from(resp):
        if _get_role(m) == "ai":
            text = _get_content(m).strip()
            if text:
                return text
    return ""


def _print_plan(plan_text: str):
    print("AI (PLAN):")
    print(plan_text.strip())


def _print_exec_transcript(resp, *, show_tool_output: bool, max_lines: int = 120):
    def trunc(s: str) -> str:
        lines = (s or "").rstrip().splitlines()
        return "\n".join(lines if len(lines) <= max_lines else lines[:max_lines] + ["... [truncated]"])

    for m in _messages_from(resp):
        role = _get_role(m)
        text = _get_content(m)
        if not text:
            continue
        if role == "ai":
            print("AI:", trunc(text))
        elif role == "tool" and show_tool_output:
            name = ""
            if isinstance(m, dict):
                name = m.get("name") or m.get("tool_name") or ""
            else:
                name = getattr(m, "name", "") or getattr(m, "tool_name", "") or ""
            print(f"TOOL{f'({name})' if name else ''}:")
            print(trunc(text))


def ai(
    query: str = typer.Argument(..., help="e.g. 'init alembic and create migrations'"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm execution"),
    interactive: bool = typer.Option(True, help="HITL approval per tool call"),
    temperature: float = typer.Option(0.0, help="LLM creativity"),
    show_tool_output: bool = typer.Option(True, help="Print terminal output from tools"),
):
    agent = CoreAgent()

    # ---- Phase 1: PLAN (no tools) ----
    plan_messages = [
        {"role": "system", "content": _read_readme()},
        {"role": "system", "content": PLAN_POLICY},
        {"role": "human",  "content": query},
    ]
    plan_resp = agent.run_agent(
        messages=plan_messages,
        provider=Providers.openai,
        model_name=Models.openai.gpt_5_mini.value,
        tools=[],
        model_kwargs={"temperature": temperature},
    )
    plan_text = _first_ai_text(plan_resp)
    if not plan_text:
        print("AI (PLAN): (no plan parsed) RAW BELOW\n", plan_resp)
        return
    _print_plan(plan_text)

    proceed = yes or input("\nProceed with execution? [y/N]: ").strip().lower() in ("y", "yes")
    if not proceed:
        print("Aborted. (Nothing executed.)")
        return

    # ---- Phase 2: EXECUTE (tools + HITL) ----
    agent.set_hitl(on_tool_call=agent.make_sys_gate(interactive))
    exec_messages = [
        {"role": "system", "content": _read_readme()},
        {"role": "system", "content": EXEC_POLICY},
        {"role": "human",  "content": "Execute this plan now:\n" + plan_text},
    ]
    exec_resp = agent.run_agent(
        messages=exec_messages,
        provider=Providers.openai,
        model_name=Models.openai.gpt_5_mini.value,
        tools=[run_command],
        model_kwargs={"temperature": temperature},
    )

    print("\n=== EXECUTION ===")
    _print_exec_transcript(exec_resp, show_tool_output=show_tool_output)

