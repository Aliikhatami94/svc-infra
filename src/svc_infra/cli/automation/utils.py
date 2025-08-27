import re
import typer
from ai_infra.llm.providers import Providers, Models


# ---- Console output helpers ---- #

def _print_success(msg: str) -> None:
    # Force color even when not a TTY (e.g., piped or captured)
    typer.secho(msg, fg=typer.colors.GREEN, bold=True, color=True)

def _print_warning(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.YELLOW, bold=True, color=True)

def _print_error(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, bold=True, color=True)


# ---- Redaction helpers ---- #

_SECRET_RE = re.compile(
    r'(?P<scheme>\b[a-zA-Z][a-zA-Z0-9+\-.]*://)'
    r'(?:(?P<user>[^:/\s@]+)(?::(?P<pw>[^@\s]+))?@)?'
)
# Additional redaction patterns
_SQL_PASSWORD_QUOTED_RE = re.compile(r"(?i)(password\s*)(['\"])[^'\"]*(\2)")
_EQ_PASSWORD_QUOTED_RE = re.compile(r"(?i)(password\s*=\s*)(['\"])[^'\"]*(\2)")
_CLI_PASSWORD_EQ_RE = re.compile(r"(?i)(--password\s*=\s*)([^\s]+)")
_CLI_PASSWORD_SPACE_RE = re.compile(r"(?i)(--password)(\s+)([^\s]+)")
_ENV_PGPASSWORD_RE = re.compile(r"(?i)(pgpassword\s*=\s*)([^\s]+)")

def _redact_secrets(text: str) -> str:
    def _sub(m):
        scheme = m.group("scheme") or ""
        user = m.group("user")
        return f"{scheme}***:***@" if user else scheme
    return _SECRET_RE.sub(_sub, text or "")

def _redact(text: str) -> str:
    """Redact secrets in URLs and common CLI/SQL password patterns."""
    t = _redact_secrets(text or "")
    t = _SQL_PASSWORD_QUOTED_RE.sub(r"\1'***'", t)
    t = _EQ_PASSWORD_QUOTED_RE.sub(r"\1'***'", t)
    t = _CLI_PASSWORD_EQ_RE.sub(r"\1***", t)
    # Normalize space form to equals form while redacting
    t = _CLI_PASSWORD_SPACE_RE.sub(r"\1=***", t)
    t = _ENV_PGPASSWORD_RE.sub(r"\1***", t)
    return t


# ---- AI message helpers ---- #

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


# ---- Error parsing helpers ---- #

_ERR_CODE_RE = re.compile(r"Command failed with code (\d+)")
_LAST_LINE_RE = re.compile(r"(?:\n|^)([A-Za-z0-9_:. -]*Error[:] ?.+)$")
_DOCKER_DAEMON_RE = re.compile(r"Cannot connect to the Docker daemon.*", re.I)
_PG_ROLE_RE = re.compile(r"role [\"']?([A-Za-z0-9_]+)[\"']? does not exist", re.I)
_SQLA_URL_RE = re.compile(r"Could not parse SQLAlchemy URL.*", re.I)
# Homebrew errors
_BREW_NOT_FOUND_RE = re.compile(r"brew: command not found", re.I)
_BREW_SERVICE_ERROR_RE = re.compile(r"Error: .*brew services.*", re.I)
_BREW_SERVICES_UNKNOWN_CMD_RE = re.compile(r"Unknown command: services\b", re.I)
_BREW_SERVICE_HINT_RE = re.compile(r"Did you mean:.*\bservice\b", re.I)

def _summarize_tool_error(text: str) -> str:
    t = text or ""
    tl = t.lower()
    # Common, recognizable reasons
    if _DOCKER_DAEMON_RE.search(t):
        return "Docker daemon not reachable"
    if _PG_ROLE_RE.search(t):
        who = _PG_ROLE_RE.search(t).group(1)
        return f"Postgres role '{who}' does not exist"
    if _SQLA_URL_RE.search(t):
        return "Invalid or empty SQLAlchemy DATABASE_URL"
    if "unknown user 'postgres'" in tl:
        return "Postgres system user not available on this host"
    if _BREW_NOT_FOUND_RE.search(t):
        return "Homebrew not installed or not in PATH"
    if _BREW_SERVICE_ERROR_RE.search(t) or _BREW_SERVICES_UNKNOWN_CMD_RE.search(t) or _BREW_SERVICE_HINT_RE.search(t):
        return "Homebrew service command failed"

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


# ---- Transcript printing ---- #

def _print_exec_transcript(resp, *, show_tool_output: bool, max_lines: int = 60, quiet_tools: bool = False, show_error_context: bool = True):
    def _is_noise(s: str) -> bool:
        return "run:: command not found" in (s or "").lower()

    def _trunc(s: str, n: int) -> str:
        lines = (s or "").rstrip().splitlines()
        return "\n".join(lines if len(lines) <= n else lines[:n] + ["... [truncated]"])

    # Pre-scan to count total RUN steps (skip duplicate echoes)
    total_steps = 0
    scan_last_cmd = None
    for _m in _messages_from(resp):
        if _get_role(_m) != "ai":
            continue
        t = _get_content(_m) or ""
        for _line in t.splitlines():
            _s = _line.strip()
            if not _s or not _s.startswith("RUN:"):
                continue
            raw = _s[4:].strip()
            if scan_last_cmd is not None and raw == scan_last_cmd:
                continue
            total_steps += 1
            scan_last_cmd = raw

    # Suppress trivial, redundant tool outputs
    _TRIVIAL_TOOL_LINES = {
        "Service already started.",
        "Nothing to do.",
        "Already up-to-date.",
    }

    def _print_tool_output_block(name: str, text: str, *, last_fail: bool) -> None:
        """Print tool output with spacing and summaries; hide header for non-errors."""
        if text is None:
            return
        stripped = (text or "").strip()
        if not stripped or _is_noise(stripped):
            return
        # Error summaries
        if stripped.startswith("Error:"):
            summary = _summarize_tool_error(text)
            print()
            if last_fail:
                typer.secho((f"TOOL({name}): " if name else "TOOL: ") + summary, fg=typer.colors.RED, bold=True, color=True)
            else:
                print((f"TOOL({name}): " if name else "TOOL: ") + summary)
            if summary and show_error_context and last_fail:
                print("\n🔍 Context:")
                print(_trunc(_redact(text), 20))
            if summary and "Postgres system user" in summary:
                print("* TIP: Run this on Linux, or use `--docker` to generate a docker-based workflow.")
            print()
            return
        # Non-error: print raw output only (no header)
        print(_trunc(_redact(text), max_lines))

    # -------- Collect steps first (RUN -> status -> optional NEXT lines -> tool outputs) --------
    steps: list[dict] = []
    last_cmd_raw: str | None = None
    current_step: dict | None = None
    pending_tool_outputs: list[dict] = []  # tool outputs seen before first RUN
    next_tool_step_idx = 0  # pointer to the next step expecting tool output

    for m in _messages_from(resp):
        role = _get_role(m)
        if role == "ai":
            text = _get_content(m) or ""
            if not text:
                continue
            for line in text.splitlines():
                s = line.strip()
                if not s:
                    continue
                if s.startswith("RUN:"):
                    raw_cmd = s[4:].strip()
                    if last_cmd_raw is not None and raw_cmd == last_cmd_raw:
                        continue
                    last_cmd_raw = raw_cmd
                    current_step = {
                        "cmd_raw": raw_cmd,
                        "cmd": _redact(raw_cmd),
                        "ok": False,
                        "fail_msg": None,
                        "next_header": None,
                        "bullets": [],
                        "tool_outputs": [],
                    }
                    # Attach at most one pending tool output to this step (preserve order)
                    if pending_tool_outputs:
                        current_step["tool_outputs"].append(pending_tool_outputs.pop(0))
                    steps.append(current_step)
                elif s == "OK":
                    if current_step is not None:
                        current_step["ok"] = True
                elif s.startswith("FAIL:"):
                    if current_step is not None:
                        current_step["fail_msg"] = s[5:].strip()
                elif s.startswith("NEXT:"):
                    if current_step is not None:
                        current_step["next_header"] = s[5:].strip()
                elif s.startswith("- "):
                    if steps:
                        steps[-1].setdefault("bullets", []).append(s)
                else:
                    # Ignore any other AI chatter like summaries/echoes
                    continue
            continue

        if role == "tool" and show_tool_output and not quiet_tools:
            name = (
                    (m.get("name") if isinstance(m, dict) else getattr(m, "name", ""))
                    or (m.get("tool_name") if isinstance(m, dict) else getattr(m, "tool_name", ""))
            )
            text = _get_content(m) or ""
            if steps:
                # Find next step without anassigned output
                while next_tool_step_idx < len(steps) and steps[next_tool_step_idx]["tool_outputs"]:
                    next_tool_step_idx += 1
                target_idx = min(next_tool_step_idx, len(steps) - 1)
                steps[target_idx]["tool_outputs"].append({"name": name, "text": text})
                # Advance pointer if we just filled a step
                if target_idx == next_tool_step_idx and steps[target_idx]["tool_outputs"]:
                    next_tool_step_idx += 1
            else:
                # Buffer outputs until a RUN step arrives
                pending_tool_outputs.append({"name": name, "text": text})

    # -------- Print steps (Step -> output -> status) --------
    for i, step in enumerate(steps, start=1):
        if not step.get("cmd") and not step.get("tool_outputs"):
            continue
        if step.get("cmd"):
            typer.secho(f"Step {i}: {step['cmd']}", fg=typer.colors.YELLOW, bold=True, color=True)
        # Tool outputs first (immediately under the step)
        if show_tool_output and not quiet_tools:
            for idx, out in enumerate(step.get("tool_outputs", [])):
                # Pass whether this step failed so context prints when appropriate
                _print_tool_output_block(out.get("name"), out.get("text"), last_fail=bool(step.get("fail_msg")))
        # Then status
        if step.get("ok"):
            _print_success("OK\n")
        elif step.get("fail_msg"):
            _print_error(f"Step {i} failed: {step['fail_msg']}\n")
            if "Postgres system user" in step["fail_msg"]:
                print("* TIP: Run this on Linux, or use `--docker` to generate a docker-based workflow.")
        # NEXT and bullets
        if step.get("next_header"):
            print("\n* " + step["next_header"])
        for b in step.get("bullets", []):
            print(" " + b)


# ------------- plan printing helper -------------

def _print_numbered_plan(plan_text: str) -> None:
    cmds: list[str] = []
    for line in (plan_text or "").splitlines():
        raw = (line or "").strip()
        if not raw:
            continue
        m = re.match(r"^\s*(\d+)[)\.\]]\s*(.*)$", raw)
        if m:
            cmds.append(m.group(2).strip())
            continue
        m2 = re.match(r"^\s*[-*]\s+(.*)$", raw)
        if m2:
            cmds.append(m2.group(1).strip())
            continue
        cmds.append(raw)
    typer.secho("Plan:", fg=typer.colors.BLUE, bold=True, color=True)
    for i, cmd in enumerate(cmds, start=1):
        typer.secho(f"{i}. {cmd}", fg=typer.colors.BLUE, color=True)

def clip(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    cut = cut[: cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip() + "..."

# ----- Provider/model resolution helpers ---- #

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