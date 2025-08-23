from __future__ import annotations

from pathlib import Path
from alembic.config import Config
from alembic import command


def _cfg(cwd: str = ".") -> Config:
    cfg = Config(str(Path(cwd) / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(cwd) / "migrations"))
    return cfg


def init_migrations(cwd: str = ".") -> None:
    command.init(_cfg(cwd), str(Path(cwd) / "migrations"))


def make_migration(msg: str = "auto", cwd: str = ".") -> None:
    command.revision(_cfg(cwd), message=msg, autogenerate=True)


def upgrade(head: str = "head", cwd: str = ".") -> None:
    command.upgrade(_cfg(cwd), head)


def downgrade(target: str = "-1", cwd: str = ".") -> None:
    command.downgrade(_cfg(cwd), target)

