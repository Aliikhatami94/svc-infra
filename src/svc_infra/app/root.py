# svc_infra/cli/project_root.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional

# You (or users) can drop this file at the project root to force the answer.
SENTRY_FILES: tuple[str, ...] = (
    # VCS
    ".git",
    ".hg",
    ".svn",
    # Alembic
    "alembic.ini",
    "migrations/env.py",
    "migrations/script.py.mako",
    "migrations",
    # Python project “roots”
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "Pipfile",
    "requirements.txt",
    "tox.ini",
    ".editorconfig",
    # Lock files (various tools)
    "poetry.lock",
    "pdm.lock",
    "uv.lock",
    "hatch.toml",
    # Common layouts
    "src",
    "app",
    "backend",
    # Explicit escape hatch
    ".svc-infra-root",
)

ENV_VAR = "SVC_INFRA_PROJECT_ROOT"


def _is_root_marker(dir_: Path, sentries: Iterable[str]) -> bool:
    for name in sentries:
        p = dir_ / name
        # Treat directories like migrations/ & src/ as markers too
        if p.exists():
            return True
    return False


def _git_toplevel(start: Path) -> Optional[Path]:
    """Use git if available; safe no-op if not a repo."""
    try:
        if not shutil.which("git"):  # type: ignore[name-defined]
            return None
    except Exception:
        return None
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            stderr=subprocess.DEVNULL,
        )
        path = Path(out.decode().strip())
        return path if path.exists() else None
    except Exception:
        return None


def resolve_project_root(
        start: Optional[Path] = None,
        *,
        env_var: str = ENV_VAR,
        extra_sentries: Iterable[str] = (),
) -> Path:
    """
    Heuristically resolve a project root, tool-agnostic.

    Order of precedence:
      1) explicit env var SVC_INFRA_PROJECT_ROOT
      2) VCS root (git rev-parse --show-toplevel)
      3) walk upward from `start` (or CWD) until a directory contains any “sentry” file/dir
      4) fallback to `start` (or CWD)

    Notes:
      - You can drop an empty `.svc-infra-root` at your desired root to force it.
      - `extra_sentries` lets callers inject additional markers if needed.
    """
    # 1) Environment override
    env = os.getenv(env_var)
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p

    # default start
    start = (start or Path.cwd()).resolve()

    # 2) VCS (git) quickest path to the real top
    git_root = _git_toplevel(start)
    if git_root:
        return git_root

    # 3) Walk upward looking for any sentry
    sentries: tuple[str, ...] = tuple(SENTRY_FILES) + tuple(extra_sentries)
    for d in [start, *start.parents]:
        if _is_root_marker(d, sentries):
            return d

    # 4) Last resort
    return start


# Optional: tiny stdlib fallback for shutil.which in older pythons/import order.
try:
    import shutil  # noqa: E402
except Exception:
    class _Which:
        def which(self, *_args, **_kwargs):
            return None
    shutil = _Which()  # type: ignore