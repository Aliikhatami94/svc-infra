from __future__ import annotations
import os, subprocess
from pathlib import Path
from typing import Iterable, Optional

SENTRY_FILES: tuple[str, ...] = (
    # VCS
    ".git", ".hg", ".svn",
    # Alembic
    "alembic.ini", "migrations/env.py", "migrations/script.py.mako", "migrations",
    # Python project roots
    "pyproject.toml", "setup.cfg", "setup.py", "Pipfile", "requirements.txt",
    "tox.ini", ".editorconfig",
    # Locks
    "poetry.lock", "pdm.lock", "uv.lock", "hatch.toml",
    # Common layouts
    "src", "app", "backend",
    # Explicit override marker
    ".svc-infra-root",
)
ENV_VAR = "SVC_INFRA_PROJECT_ROOT"

def _is_root_marker(dir_: Path, sentries: Iterable[str]) -> bool:
    return any((dir_ / name).exists() for name in sentries)

def _git_toplevel(start: Path) -> Optional[Path]:
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
        p = Path(out.decode().strip())
        return p if p.exists() else None
    except Exception:
        return None

def resolve_project_root(
        start: Optional[Path] = None,
        *,
        env_var: str = ENV_VAR,
        extra_sentries: Iterable[str] = (),
) -> Path:
    # 1) explicit env var
    env = os.getenv(env_var)
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p

    # 2) starting point
    start = (start or Path.cwd()).resolve()

    # 3) git toplevel (fast & correct for most repos)
    git_root = _git_toplevel(start)
    if git_root:
        return git_root

    # 4) walk upward for markers
    sentries = tuple(SENTRY_FILES) + tuple(extra_sentries)
    for d in [start, *start.parents]:
        if _is_root_marker(d, sentries):
            return d

    # 5) fallback
    return start

# minimal which fallback if needed
try:
    import shutil  # noqa
except Exception:
    class _Which:
        def which(self, *_args, **_kwargs):
            return None
    shutil = _Which()  # type: ignore