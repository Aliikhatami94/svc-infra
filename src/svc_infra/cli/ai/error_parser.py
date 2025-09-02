import re

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

def extract_last_fail(messages) -> tuple[str|None, str|None]:
    """
    Return (cmd_raw, fail_summary) from an LLM/agent response messages list.
    Very small heuristic based on RUN/OK/FAIL lines emitted by your EXEC policy.
    """
    cmd = None
    fail = None
    # normalize
    def _role(m): return (m.get("role") or m.get("type") or "").lower() if isinstance(m, dict) else (getattr(m, "role", "") or "").lower()
    def _text(m): return (m.get("content") or "") if isinstance(m, dict) else (getattr(m, "content", "") or "")
    # find last RUN and the next FAIL
    last_cmd = None
    for m in messages or []:
        if _role(m) != "ai":
            continue
        for line in (_text(m) or "").splitlines():
            s = line.strip()
            if s.startswith("RUN:"):
                last_cmd = s[4:].strip()
            elif s.startswith("FAIL:"):
                cmd = last_cmd
                # summarize
                tail = s[5:].strip()
                mcode = _ERR_CODE_RE.search(tail)
                summary = f"code {mcode.group(1)}" if mcode else tail
                fail = summary or "command failed"
    return cmd, fail