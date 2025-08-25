from __future__ import annotations

from pathlib import Path
import os
import re
import typer
from ai_infra import Providers, Models
from ai_infra.llm import CoreAgent, CoreLLM
from ai_infra.llm.tools.custom.terminal import run_command


# -------------------- context --------------------

def _read_readme() -> str:
    p = Path(__file__).parent / "README.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""

# Super-compact, low-token policies
PLAN_POLICY = (
    "ROLE=db-cli\n"
    "TASK=PLAN\n"
    "Output ONLY a short, numbered list of exact shell commands. Do not execute. No notes."
)

EXEC_POLICY = (
    "ROLE=db-cli\n"
    "TASK=EXEC\n"
    "Loop: print 'RUN: <command>'; call terminal tool with RAW command; then print 'OK' or 'FAIL: <reason>'. "
    "Never echo secrets. One-shot. Optional final 'NEXT:' with 1–3 bullets."
)

EXEC_DIRECT_POLICY = (
    "ROLE=db-cli\n"
    "TASK=EXEC_DIRECT\n"
    "Choose minimal commands; same loop as EXEC. One-shot. Optional 'NEXT:'."
)

# -------------------- transcript helpers --------------------

_SECRET_RE = re.compile(
    r'(?P<scheme>\b[a-zA-Z][a-zA-Z0-9+\-.]*://)'
    r'(?:(?P<user>[^:/\s@]+)(?::(?P<pw>[^@\s]+))?@)?'
)

def _redact_secrets(text: str) -> str:
    def _sub(m):
        scheme = m.group("scheme") or ""
        user = m.group("user")
        return f"{scheme}***:***@" if user else scheme
    return _SECRET_RE.sub(_sub, text or "")

def _norm_role(role: str) -> str:
    r = (role or "").lower()
    return "ai" if r == "assistant" else r

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


# ---------- compact error summarization for tool output ----------

_ERR_CODE_RE = re.compile(r"Command failed with code (\d+)")
_LAST_LINE_RE = re.compile(r"(?:\n|^)([A-Za-z0-9_:. -]*Error[:]? .+)$")
_DOCKER_DAEMON_RE = re.compile(r"Cannot connect to the Docker daemon.*", re.I)
_PG_ROLE_RE = re.compile(r"role [\"']?([A-Za-z0-9_]+)[\"']? does not exist", re.I)
_SQLA_URL_RE = re.compile(r"Could not parse SQLAlchemy URL.*", re.I)

def _summarize_tool_error(text: str) -> str:
    t = text or ""
    # Common, recognizable reasons
    if _DOCKER_DAEMON_RE.search(t):
        return "Docker daemon not reachable"
    if _PG_ROLE_RE.search(t):
        who = _PG_ROLE_RE.search(t).group(1)
        return f"Postgres role '{who}' does not exist"
    if _SQLA_URL_RE.search(t):
        return "Invalid or empty SQLAlchemy DATABASE_URL"

    # Capture exit code
    m = _ERR_CODE_RE.search(t)
    code = m.group(1) if m else None

    # Heuristic: last line that looks like an error
    m2 = _LAST_LINE_RE.findall(t)
    tail = m2[-1].strip() if m2 else ""

    if code and tail:
        return f"code {code}: {tail}"
    if code:
        return f"code {code}"
    return tail or "command failed"

def _print_exec_transcript(resp, *, show_tool_output: bool, max_lines: int = 60, quiet_tools: bool = False):
    def _is_noise(s: str) -> bool:
        return "run:: command not found" in (s or "").lower()

    def _trunc(s: str, n: int) -> str:
        lines = (s or "").rstrip().splitlines()
        return "\n".join(lines if len(lines) <= n else lines[:n] + ["... [truncated]"])

    for m in _messages_from(resp):
        role = _get_role(m)
        text = _get_content(m) or ""
        if not text:
            continue

        if role == "ai":
            kept = []
            for line in text.splitlines():
                s = line.strip()
                if (
                        s.startswith("RUN:")
                        or s == "OK"
                        or s.startswith("FAIL:")
                        or s.startswith("NEXT:")
                        or s.startswith("- ")
                ):
                    kept.append(line)

            if kept:
                # Insert a spacer before NEXT: if it’s mixed with RUN/OK/FAIL
                formatted = []
                for l in kept:
                    if l.strip().startswith("NEXT:") and (len(formatted) == 0 or formatted[-1].strip() != ""):
                        formatted.append("")  # blank line before NEXT
                    formatted.append(l)

                print("AI:", "\n".join(formatted))
                print()  # always blank line after AI block
            continue

        if role == "tool" and show_tool_output and not quiet_tools:
            if _is_noise(text):
                continue
            name = (
                    (m.get("name") if isinstance(m, dict) else getattr(m, "name", ""))
                    or (m.get("tool_name") if isinstance(m, dict) else getattr(m, "tool_name", ""))
            )

            if text.strip().startswith("Error:"):
                print(f"TOOL{f'({name})' if name else ''}: " + _summarize_tool_error(text))
            else:
                print(f"TOOL{f'({name})' if name else ''}:")
                print(_trunc(_redact_secrets(text), max_lines))

            print()


# -------------------- helpers for provider/model resolution --------------------

def _norm_key(s: str) -> str:
    return (s or "").strip().lower().replace("-", "_")

def _resolve_provider(provider_key: str):
    key = _norm_key(provider_key)
    prov = getattr(Providers, key, None)
    if prov is None:
        # show a short list of known providers
        known = [k for k in dir(Providers) if not k.startswith("_")]
        raise typer.BadParameter(f"Unknown provider '{provider_key}'. Known: {', '.join(sorted(known))}")
    return prov, key  # also return normalized key for Models lookup

def _resolve_model(models_key: str, model_key: str) -> str:
    ns = getattr(Models, models_key, None)
    if ns is None:
        raise typer.BadParameter(f"No models found for provider '{models_key}'.")
    if not model_key or model_key == "default":
        return ns.default.value
    mk = _norm_key(model_key)
    candidate = getattr(ns, mk, None)
    if candidate is None:
        # list available names on that provider
        available = [k for k in dir(ns) if not k.startswith("_")]
        raise typer.BadParameter(
            f"Unknown model '{model_key}' for provider '{models_key}'. "
            f"Available: {', '.join(sorted(available))}"
        )
    return candidate.value


# ------- tool guards and composition with base gate ----

def _guard_run_command(args: dict):
    """Return an action dict to short-circuit, or None to defer to base gate."""
    cmd = (args or {}).get("command", "") or ""
    s = cmd.strip().lower()
    if not cmd:
        return {"action": "block", "replacement": "[blocked: empty command]"}
    if s.startswith("run:"):
        return {"action": "block", "replacement": "[ignored RUN: prefix — assistant text only]"}
    return None  # no opinion; let base gate decide


def _with_tool_guards(base_gate, guards: dict[str, callable]):
    """Compose per-tool guards with the generic base gate."""
    def gate(tool_name: str, args: dict):
        g = guards.get(tool_name)
        if g:
            decision = g(args or {})
            if isinstance(decision, dict):  # short-circuit if guard returns an action
                return decision
        return base_gate(tool_name, args)
    return gate

# -------------------- CLI --------------------

def ai(
        query: str = typer.Argument(..., help="e.g. 'init alembic and create migrations'"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm plan execution"),
        autoapprove: bool = typer.Option(False, "--autoapprove", help="Auto-approve all tool calls"),
        auto: bool = typer.Option(False, "--auto", help="Fully autonomous: approve plan + tool calls"),
        db_url: str = typer.Option("", "--db-url", help="Set $DATABASE_URL for tools (never printed)"),
        require_db: bool = typer.Option(False, "--require-db", help="Fail fast if no DB URL available"),
        max_lines: int = typer.Option(60, "--max-lines", help="Max lines when printing tool output"),
        quiet_tools: bool = typer.Option(False, "--quiet-tools", help="Hide tool output; show only AI summaries"),
        provider: str = typer.Option("openai", "--provider", help="LLM provider (e.g. openai, anthropic, google)"),
        model: str = typer.Option("default", "--model", help="Model name key (e.g. gpt_5_mini, sonnet, gemini_1_5_pro)"),
):
    """
    AI-powered DB assistant (stateless, one-shot).

    Modes:
      - default: PLAN → confirm → EXECUTE (manual HITL per tool)
      - --autoapprove: PLAN → confirm → EXECUTE (autoapprove tools)
      - --auto: PLAN → autoapprove → EXECUTE (autoapprove tools)
    """
    # Promote auto → autoapprove + yes
    if auto:
        autoapprove = True
        yes = True

    prov, models_key = _resolve_provider(provider)
    model_name = _resolve_model(models_key, model)

    if require_db and not (db_url or os.environ.get("DATABASE_URL", "")):
        print("FAIL: No database URL available. Provide --db-url or set $DATABASE_URL.")
        return

    if db_url:
        os.environ["DATABASE_URL"] = db_url

    llm = CoreLLM()
    agent = CoreAgent()

    # -------- PLAN --------
    sys_prompt = _read_readme() + "\n\n" + PLAN_POLICY
    plan_text = llm.chat(
        user_msg=query,
        system=sys_prompt,
        provider=prov,
        model_name=model_name,
    ).content

    if not plan_text:
        print("AI (PLAN): (no plan parsed)")
        return

    print(plan_text)

    if not yes:
        proceed = input("\nProceed with execution? [y/N]: ").strip().lower() in ("y", "yes")
        if not proceed:
            print("Aborted. (Nothing executed.)")
            return

    # -------- EXECUTE --------
    base_gate = agent.make_sys_gate(autoapprove=autoapprove)
    guarded_gate = _with_tool_guards(base_gate, {"run_command": _guard_run_command})
    agent.set_hitl(on_tool_call=guarded_gate)

    exec_guidance = (
        "If a DB connection is needed, prefer: --database-url \"$DATABASE_URL\" (never echo its value)."
    )

    exec_messages = [
        {"role": "system", "content": _read_readme()},
        {"role": "system", "content": EXEC_POLICY},
        {"role": "human",  "content": f"{exec_guidance}\n\nExecute this plan now:\n{plan_text}"},
    ]

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
    )