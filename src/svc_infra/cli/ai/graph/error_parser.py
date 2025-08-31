import re


_ERR_CODE_RE = re.compile(r"Command failed with code (\d+)")
_LAST_LINE_RE = re.compile(r"(?:\n|^)([A-Za-z0-9_:. -]*Error[:] ?.+)$")

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