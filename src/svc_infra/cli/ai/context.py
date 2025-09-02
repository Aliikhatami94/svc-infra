import sys
from typing import Any

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

from svc_infra.cli.ai.utils import _redact


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

_PROJECT_SIGNALS = {
    # Build / package managers
    "python": ["pyproject.toml", "poetry.lock", "requirements.txt", "setup.py"],
    "node":   ["package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"],
    "java":   ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
    "docker": ["Dockerfile", "docker-compose.yml", "compose.yml"],
    "make":   ["Makefile"],
    "just":   ["Justfile"],
    "task":   ["Taskfile.yml", "Taskfile.yaml"],
    "pytest": ["pytest.ini", "pyproject.toml"],
}

def _scan_project_signals(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for key, files in _PROJECT_SIGNALS.items():
        hits = [f for f in files if (root / f).exists()]
        if hits:
            found[key] = hits
    return found

def _capabilities_text(root: Path) -> str:
    hits = []
    if (root / "pyproject.toml").exists(): hits.append("Python/Poetry")
    elif (root / "requirements.txt").exists(): hits.append("Python/pip")
    if (root / "package.json").exists(): hits.append("Node (npm/yarn/pnpm)")
    if (root / "pom.xml").exists(): hits.append("Java/Maven")
    if any((root / f).exists() for f in ("build.gradle","build.gradle.kts")): hits.append("Java/Gradle")
    if any((root / f).exists() for f in ("Dockerfile","docker-compose.yml","compose.yml")): hits.append("Docker")
    if (root / "Makefile").exists(): hits.append("Make")
    if (root / "Justfile").exists(): hits.append("Just")
    if any((root / f).exists() for f in ("Taskfile.yml","Taskfile.yaml")): hits.append("Taskfile")
    # tools on PATH:
    for tool in ("poetry","npm","yarn","pnpm","mvn","gradle","docker","make","just","task","svc-infra"):
        if shutil.which(tool): hits.append(f"{tool} (on PATH)")
    return "## Capabilities\n- " + "\n- ".join(sorted(set(hits))) + "\n" if hits else ""

def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    signals = ("pyproject.toml","package.json","pom.xml","build.gradle",
               ".git","Makefile","Justfile","Taskfile.yml","Taskfile.yaml","Dockerfile","docker-compose.yml","compose.yml")
    while True:
        if any((cur / s).exists() for s in signals):
            return cur
        if cur.parent == cur:
            return start.resolve()
        cur = cur.parent

def _discover_package_context() -> dict[str, Any]:
    """
    Discover any packages that expose a CLI entry under src/svc_infra/**/core.py.

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

    cli_files = list((root / "src" / "svc_infra").glob("**/core.py"))

    packages: list[dict[str, str]] = []
    for cli_file in cli_files:
        pkg_dir = cli_file.parent
        module = pkg_dir.name
        # Build conventional package name
        pkg_name = f"svc-infra {module}"
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

def _run_quiet(args: list[str], cwd: Path | None = None) -> str:
    try:
        out = subprocess.check_output(args, cwd=str(cwd) if cwd else None, text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except Exception:
        return ""

def _git_ahead_behind(root: Path, upstream: str) -> str:
    out = _run_quiet(["git","rev-list","--left-right","--count",f"{upstream}...HEAD"], cwd=root)
    if not out: return ""
    left,right = (out.split() + ["0","0"])[:2]
    return f"{right} ahead / {left} behind"

def _git_context(root: Path) -> str:
    top = _run_quiet(["git", "rev-parse", "--show-toplevel"], cwd=root)
    if not top:
        return ""
    branch = _run_quiet(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    upstream = _run_quiet(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=root)
    ahead_behind = _git_ahead_behind(root, upstream)
    log = _run_quiet(["git", "--no-pager", "log", "--oneline", "-n", "3"], cwd=root)
    remotes = _redact(_run_quiet(["git", "remote", "-v"], cwd=root))
    return (
            "## Git\n"
            f"Repo root: {top}\n"
            f"Branch: {branch or 'unknown'}"
            + (f" | Upstream: {upstream}" if upstream else "")
            + (f" | Ahead/Behind: {ahead_behind}" if ahead_behind else "")
            + "\n\n```text\n"
              f"{remotes}\n\nRecent commits:\n{log}\n```\n"
    )

PLAN_POLICY = (
    "ROLE=repo-orchestrator\n"
    "TASK=PLAN\n"
    "Assume working directory is the repo root: ${REPO_ROOT}.\n"
    "Output ONLY a short, numbered list of exact shell commands (one per line). "
    "No prose, no comments, no code fences.\n"
    "Prefer local tools inferred from project signals (svc-infra, poetry, npm/yarn/pnpm, mvn/gradle, make, docker compose). "
    "If a command isn’t on PATH and pyproject.toml exists, try `poetry run <cmd>` first.\n"
    "Avoid destructive operations (rm -rf, sudo) unless explicitly requested."
)

def cli_planner_sys_msg() -> str:
    ctx = _discover_package_context()
    root = Path(ctx["root"])

    git_txt  = _git_context(root)
    caps_txt = _capabilities_text(root)
    os_hint = _os_hint()

    return git_txt + caps_txt + os_hint + PLAN_POLICY