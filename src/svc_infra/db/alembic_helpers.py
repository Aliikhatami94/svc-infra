from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional


def _alembic(cmd: str, *, cwd: str = ".", env: Optional[dict[str, str]] = None) -> int:
    e = os.environ.copy()
    e.setdefault("PYTHONPATH", os.getcwd())
    if env:
        e.update(env)
    return subprocess.check_call([sys.executable, "-m", "alembic"] + cmd.split(), cwd=cwd, env=e)


def init_migrations(cwd: str = ".") -> int:
    return _alembic("init migrations", cwd=cwd)


def make_migration(msg: str = "auto", cwd: str = ".") -> int:
    return _alembic(f"revision --autogenerate -m {msg!r}", cwd=cwd)


def upgrade(head: str = "head", cwd: str = ".") -> int:
    return _alembic(f"upgrade {head}", cwd=cwd)


def downgrade(target: str = "-1", cwd: str = ".") -> int:
    return _alembic(f"downgrade {target}", cwd=cwd)

