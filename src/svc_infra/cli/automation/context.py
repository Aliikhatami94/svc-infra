import sys
from typing import Any

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

# Directories we usually don't want to expand
_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "node_modules", ".venv", "venv", ".tox",
    "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".next", ".turbo", ".cache", ".gradle",
}

# Files we usually don't care to list (big or noisy)
_IGNORED_FILES = {
    ".DS_Store",
}

def _iter_dir(path: Path) -> Iterable[Path]:
    try:
        yield from sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception:
        return

def _shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."

def _py_tree(
        root: Path,
        max_depth: int,
        max_total: int,
        max_entries_per_dir: int,
        focus_paths: Sequence[Path],
) -> str:
    """
    Python fallback: deep tree with selective focus expansion.
    Always expands items under any path that is a prefix of a focus path.
    """
    lines: list[str] = []
    total = 0

    root = root.resolve()
    focus_paths = [fp.resolve() for fp in focus_paths if isinstance(fp, Path)]

    def is_under_focus(p: Path) -> bool:
        rp = p.resolve()
        return any(str(rp).startswith(str(f)) for f in focus_paths)

    def walk(dir_path: Path, prefix: str, depth: int) -> None:
        nonlocal total
        if total >= max_total:
            return

        try:
            entries = [p for p in _iter_dir(dir_path)
                       if p.name not in _IGNORED_FILES
                       and (p.name not in _IGNORED_DIRS or is_under_focus(p))]
        except Exception:
            return

        if not entries:
            return

        shown = 0
        n = len(entries)
        for i, p in enumerate(entries, start=1):
            if total >= max_total:
                break
            if shown >= max_entries_per_dir and not is_under_focus(p):
                remaining = n - (i - 1)
                lines.append(f"{prefix}└── … ({remaining} more)")
                break

            connector = "└──" if i == n else "├──"
            label = p.name + ("/" if p.is_dir() else "")
            lines.append(f"{prefix}{connector} {_shorten(label, 120)}")
            total += 1
            shown += 1

            # Decide the recursive depth: full if in focus; else use remaining depth
            next_depth = max_depth if is_under_focus(p) else depth - 1

            if p.is_dir() and next_depth > 0:
                child_prefix = f"{prefix}{'    ' if i == n else '│   '}"
                walk(p, child_prefix, next_depth)

    lines.append(root.name + "/")
    walk(root, "", max_depth)
    return "\n".join(lines)

def render_repo_tree(
        root: Path,
        *,
        prefer_external: bool = True,
        depth_default: int = 3,
        depth_focus: int = 6,
        max_total: int = 3000,
        max_entries_per_dir: int = 80,
        focus_subpaths: Sequence[str] = ("src/svc_infra", "tests"),
) -> str:
    """
    Render a deep repo tree. If `tree` is available and prefer_external=True, use it;
    otherwise fall back to a Python renderer with selective deepening for focus paths.

    - depth_default: max depth for general dirs
    - depth_focus:   max depth for focus dirs (applies recursively under those roots)
    """
    root = root.resolve()
    focus_paths = [root / sp for sp in focus_subpaths]

    # Try using the external `tree` command if available
    if prefer_external and shutil.which("tree"):
        # Build ignore pattern for external tree (-I uses | as alternation)
        ignore_globs = [
            ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", ".venv", "venv",
            ".tox", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache",
            ".next", ".turbo", ".cache", ".gradle",
        ]
        ignore_pattern = "|".join(ignore_globs)

        # We can't express "focus deeper than default" with plain `tree`,
        # so pick the larger of the two depths to not miss structure.
        depth = max(depth_default, depth_focus)

        try:
            out = subprocess.check_output(
                ["tree", "-a", "-I", ignore_pattern, "-L", str(depth), str(root)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return out.strip()
        except Exception:
            # fall back to Python if tree invocation fails
            pass

    # Python fallback with selective deepening for focus paths
    # Strategy:
    #  - First level under root uses depth_default
    #  - Any path under a focus path expands up to depth_focus
    return _py_tree(
        root=root,
        max_depth=depth_default,
        max_total=max_total,
        max_entries_per_dir=max_entries_per_dir,
        focus_paths=focus_paths,
    )

def _find_repo_root(start: Path) -> Path:
    """Walk up from start to locate the repository root (presence of pyproject.toml)."""
    cur = start.resolve()
    while True:
        if (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            # Reached filesystem root; fallback to original start
            return start.resolve()
        cur = cur.parent

def _discover_package_context() -> dict[str, Any]:
    """
    Discover any packages that expose a CLI entry under src/svc_infra/**/cli.py.

    Returns a dictionary with keys:
      - root: repository root path
      - packages: list of { package, module, path, readme }
        where:
          package = conventional name like 'svc-infra-<module>'
          module  = folder name under src/svc_infra (e.g., db, auth)
          path    = absolute path to the package folder
          readme  = README.md contents if present, else ''
    """
    cwd = Path.cwd()
    root = _find_repo_root(cwd)

    cli_files = list((root / "src" / "svc_infra").glob("**/cli.py"))

    packages: list[dict[str, str]] = []
    for cli_file in cli_files:
        pkg_dir = cli_file.parent
        module = pkg_dir.name
        # Build conventional package name
        pkg_name = f"svc-infra-{module}"
        readme_path = pkg_dir / "README.md"
        readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        packages.append({
            "package": pkg_name,
            "module": module,
            "path": str(pkg_dir.resolve()),
            "readme": readme,
        })

    return {
        "root": str(root),
        "packages": packages,
    }

def _os_hint() -> str:
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

    return os_hint

def _compose_plan_system_prompt() -> str:
    ctx = _discover_package_context()
    root = Path(ctx["root"])

    # Render deep tree (uses `tree` if present, else Python fallback)
    tree_txt = render_repo_tree(
        root,
        depth_default=3,       # general depth
        depth_focus=6,         # deep dive under focus paths
        focus_subpaths=("src/svc_infra", "tests"),
    )

    # Package READMEs (your current logic)
    readme_snippets = "\n\n".join(
        f"# {pkg['package']} readme\n\n{pkg['readme'][:2000]}\n---"
        for pkg in ctx["packages"]
    )

    # OS hint + generic plan policy (make this non-DB specific)
    os_hint = _os_hint()  # your existing darwin/win/linux helper
    generic_plan_policy = (
        "ROLE=repo-cli\n"
        "TASK=PLAN\n"
        "Output ONLY a short, numbered list of exact shell commands. Do not execute. No notes.\n"
        "Prefer invoking available local tools (e.g., svc-infra db ..., svc-infra auth ..., npm, poetry, make, etc.)."
    )

    # Final system prompt section
    return (
            "## Project tree\n```text\n" + tree_txt + "\n```\n\n" +
            readme_snippets + "\n\n" +
            os_hint + generic_plan_policy
    )