import re, json
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List

import click
from typer.main import get_command

from svc_infra.cli.ai.utils import clip

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_WS_RE = re.compile(r"[ \t]+")

def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s or "")

def _squash_ws(s: str) -> str:
    # collapse multiple spaces/tabs and trim each line
    lines = [(line.rstrip()) for line in (s or "").splitlines()]
    lines = [_WS_RE.sub(" ", ln) for ln in lines]
    return "\n".join(lines).strip()

_SKIP = {"ai", "agent", "automation", "_internal"}

def _cmds_sorted(group: click.Group) -> list[tuple[str, click.Command]]:
    def key(kv):
        name, cmd = kv
        is_leaf = isinstance(cmd, click.Command) and not isinstance(cmd, click.Group)
        return (is_leaf, name)  # groups first
    return sorted((group.commands or {}).items(), key=key)

def _short_help(cmd: click.Command) -> str:
    sh = (getattr(cmd, "short_help", "") or "").strip()
    if sh:
        return sh.rstrip(".") + "."
    full = (getattr(cmd, "help", "") or "").strip()
    if full:
        return full.split(".")[0].strip().rstrip(".") + "."
    # last resort
    return getattr(cmd, "name", "command").replace("-", " ").capitalize() + "."

def _display_default(val):
    try:
        p = Path(str(val)).resolve()
        # hide anything under site-packages / your package / venv
        if "site-packages" in str(p) or "/svc_infra/" in str(p):
            return None
        return str(val)
    except Exception:
        return str(val)

def _option_stub(p: click.Parameter) -> str:
    if not isinstance(p, click.Option):
        return ""
    names = p.opts + p.secondary_opts
    name = "/".join(names)
    metavar = p.metavar or "VALUE"
    if p.is_flag:
        tag = "flag" + (", required" if p.required else "")
        return f"{name} ({tag})"
    default = None if (p.default is None or p.show_default is False) else _display_default(p.default)
    parts = [f"{name}=<{metavar}>"]
    if p.required: parts.append("required")
    if default is not None: parts.append(f"default: {default}")
    return parts[0] if len(parts) == 1 else f"{parts[0]} ({', '.join(parts[1:])})"

def _option_line(cmd: click.Command, max_opts: int = 8) -> str:
    if not hasattr(cmd, "params"):
        return ""
    opts = [_option_stub(p) for p in cmd.params if isinstance(p, click.Option)]
    opts = [o for o in opts if o]
    if not opts:
        return ""
    if len(opts) > max_opts:
        opts = opts[:max_opts] + ["..."]
    return "options: " + ", ".join(opts)

def _prune_inv(inv: dict, max_depth: int = 3) -> dict:
    inv = dict(inv)
    if max_depth <= 1:
        inv["subcommands"] = []
        return inv
    inv["subcommands"] = [
        _prune_inv(sc, max_depth - 1) for sc in inv.get("subcommands", [])
    ]
    return inv

def _safe_bool(v: Any) -> bool:
    try:
        return bool(v)
    except Exception:
        return False

def _build_inventory(max_depth: int = 3) -> Dict[str, Any]:
    """Walk the Typer/Click app and return a pruned command tree dict."""
    from svc_infra.cli.main import app as root_typer_app  # local import to avoid import-cycles
    root_click: click.Command = get_command(root_typer_app)

    def cmd_to_dict(cmd: click.Command, name: str) -> dict:
        d = {
            "name": name,
            "hidden": _safe_bool(getattr(cmd, "hidden", False)),
            "help": (_short_help(cmd) or ""),
            "usage": _squash_ws(cmd.get_usage(click.Context(cmd))) if hasattr(cmd, "get_usage") else "",
            "options": [],
            "subcommands": [],
        }
        if hasattr(cmd, "params"):
            for p in cmd.params:
                if isinstance(p, click.Option):
                    d["options"].append({
                        "opts": p.opts + p.secondary_opts,
                        "metavar": p.metavar,
                        "required": _safe_bool(p.required),
                        "is_flag": _safe_bool(p.is_flag),
                        "nargs": getattr(p, "nargs", None),
                    })
        if isinstance(cmd, click.Group):
            for child_name, child_cmd in _cmds_sorted(cmd):
                if child_name in _SKIP or getattr(child_cmd, "hidden", False):
                    continue
                d["subcommands"].append(cmd_to_dict(child_cmd, child_name))
        return d

    inv = cmd_to_dict(root_click, "svc-infra")
    inv = _prune_inv(inv, max_depth=max_depth)
    return inv

def _render_json(inv: Dict[str, Any]) -> str:
    return "```json\n" + json.dumps(inv, ensure_ascii=False, separators=(",", ":")) + "\n```"

def _render_md(inv: Dict[str, Any]) -> str:
    """Compact, human-readable markdown summary (like your current helper)."""
    blocks: List[str] = []
    try:
        from svc_infra.cli.main import app as root_typer_app
        root_click: click.Command = get_command(root_typer_app)

        # Root usage
        try:
            usage = _squash_ws(root_click.get_usage(click.Context(root_click)))
            blocks.append("### svc-infra — usage\n```text\n" + clip(usage, 400) + "\n```")
        except Exception:
            pass

        # Root commands list
        if isinstance(root_click, click.Group):
            lines: List[str] = []
            for name, cmd in _cmds_sorted(root_click):
                if name in _SKIP or getattr(cmd, "hidden", False):
                    continue
                lines.append(f"{name:<12} — {_short_help(cmd)}")
            if lines:
                blocks.append("### svc-infra — commands\n```text\n" + clip("\n".join(lines), 800) + "\n```")

            # Subcommand summaries (1 level)
            for name, cmd in _cmds_sorted(root_click):
                if name in _SKIP or getattr(cmd, "hidden", False):
                    continue
                try:
                    usage = _squash_ws(cmd.get_usage(click.Context(cmd)))
                    sect = [f"### svc-infra {name} — usage\n```text\n{clip(usage, 280)}\n```"]
                    if isinstance(cmd, click.Group) and (cmd.commands or {}):
                        sub_lines: List[str] = []
                        for cname, ccmd in _cmds_sorted(cmd):
                            if getattr(ccmd, "hidden", False):
                                continue
                            optline = _option_line(ccmd)
                            line = f"{cname:<16} — {_short_help(ccmd)}"
                            if optline:
                                line += f"  [{optline}]"
                            sub_lines.append(line)
                        if sub_lines:
                            sect.append("#### commands\n```text\n" + clip("\n".join(sub_lines), 800) + "\n```")
                    blocks.append("\n".join(sect))
                except Exception:
                    continue
    except Exception:
        # fall back to a very small block if anything fails
        blocks.append("### svc-infra — help\n(Help could not be rendered.)")
    return "\n\n".join(blocks)