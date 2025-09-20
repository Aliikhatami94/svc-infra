from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_SENTRIES: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    "alembic.ini",
    "migrations",
    "migrations/env.py",
    "migrations/script.py.mako",
    "pyproject.toml",
    "setup.cfg",
    "decorators.py",
    "Pipfile",
    "requirements.txt",
    "poetry.lock",
    "pdm.lock",
    "uv.lock",
    "hatch.toml",
    "src",
    "app",
    "backend",
    ".project-root",
    ".svc-infra-root",
)

ENV_VAR = "PROJECT_ROOT"


def _is_root_marker(dir_: Path, sentries: Iterable[str]) -> bool:
    return any((dir_ / name).exists() for name in sentries)


def _git_toplevel(start: Path) -> Optional[Path]:
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
    env = os.getenv(env_var)
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p

    start = (start or Path.cwd()).resolve()

    git_root = _git_toplevel(start)
    if git_root:
        return git_root

    sentries = tuple(DEFAULT_SENTRIES) + tuple(extra_sentries)
    for d in [start, *start.parents]:
        if _is_root_marker(d, sentries):
            return d

    return start
