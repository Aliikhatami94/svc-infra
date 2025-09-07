from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

# Import shared constants and utils
from svc_infra.db.setup.constants import ALEMBIC_INI_TEMPLATE, ALEMBIC_SCRIPT_TEMPLATE
from svc_infra.db.setup.utils import (
    get_database_url_from_env,
    is_async_url,
    build_engine,
    ensure_database_exists,
    prepare_process_env,
    repair_alembic_state_if_needed,
    render_env_py,
    build_alembic_config,
    ensure_db_at_head,
)

# ---------- Alembic init ----------

def _prepare_env(project_root: Path | str, *, database_url: Optional[str] = None) -> Path:
    """
    Prepare process env so Alembic can run from any host/runtime:

    - Loads .env and sets PYTHONPATH for src-layout
    - Optionally injects DATABASE_URL for this call only
    - Returns absolute project root Path
    """
    root = Path(project_root).resolve()
    prepare_process_env(root)
    if database_url:
        os.environ["DATABASE_URL"] = str(database_url)
    return root


def init_alembic(
        project_root: Path | str,
        *,
        script_location: str = "migrations",
        discover_packages: Optional[Sequence[str]] = None,
        overwrite: bool = False,
        database_url: Optional[str] = None,
) -> Path:
    """
    Initialize alembic.ini + migrations/ scaffold.

    Auto-detects async vs. sync from DATABASE_URL; defaults to sync if the URL
    can't be resolved at init time.

    Returns:
        Path to the created migrations directory.
    """
    root = _prepare_env(project_root, database_url=database_url)
    root.mkdir(parents=True, exist_ok=True)

    migrations_dir = root / script_location
    versions_dir = migrations_dir / "versions"

    alembic_ini = root / "alembic.ini"
    sqlalchemy_url = os.getenv("DATABASE_URL", "")
    dialect_name = (make_url(sqlalchemy_url).get_backend_name() if sqlalchemy_url else "")
    ini_contents = ALEMBIC_INI_TEMPLATE.format(
        script_location=script_location,
        sqlalchemy_url=sqlalchemy_url,
        dialect_name=dialect_name,
    )
    if alembic_ini.exists() and not overwrite:
        pass
    else:
        alembic_ini.write_text(ini_contents, encoding="utf-8")

    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir.mkdir(parents=True, exist_ok=True)

    script_template = migrations_dir / "script.py.mako"
    need_template_write = overwrite or not script_template.exists()
    if not need_template_write and script_template.exists():
        try:
            current = script_template.read_text(encoding="utf-8")
            if ("${upgrades" not in current) or ("${downgrades" not in current):
                need_template_write = True
        except Exception:
            need_template_write = True

    if need_template_write:
        script_template.write_text(ALEMBIC_SCRIPT_TEMPLATE, encoding="utf-8")

    pkgs = list(discover_packages or [])

    # ---- Auto-detect async from DATABASE_URL (falls back to sync if unknown)
    try:
        from sqlalchemy.engine import make_url as _make_url
        database_url = get_database_url_from_env(required=False)
        async_db = bool(database_url and is_async_url(_make_url(database_url)))
    except Exception:
        async_db = False

    env_py_text = render_env_py(pkgs, async_db=async_db)
    env_path = migrations_dir / "env.py"
    if env_path.exists() and not overwrite:
        try:
            existing = env_path.read_text(encoding="utf-8")
            if "DISCOVER_PACKAGES:" not in existing:
                env_path.write_text(env_py_text, encoding="utf-8")
        except Exception:
            env_path.write_text(env_py_text, encoding="utf-8")
    else:
        env_path.write_text(env_py_text, encoding="utf-8")

    return migrations_dir


def _ensure_db_at_head(cfg: Config) -> None:
    ensure_db_at_head(cfg)


def revision(
        project_root: Path | str,
        message: str,
        *,
        autogenerate: bool = False,
        head: str | None = "head",
        branch_label: str | None = None,
        version_path: str | None = None,
        sql: bool = False,
        ensure_head_before_autogenerate: bool = True,
) -> None:
    """
    Create a new Alembic revision.

    Example (autogenerate):
        >>> revision("..", "add orders", autogenerate=True)

    Requirements:
        - DATABASE_URL must be set in the environment.
        - Model discovery is automatic (prefers ModelBase.metadata).
    """
    database_url = get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)

    if autogenerate and ensure_head_before_autogenerate:
        if not (cfg.get_main_option("sqlalchemy.url") or os.getenv("DATABASE_URL")):
            raise RuntimeError("DATABASE_URL is not set.")
        _ensure_db_at_head(cfg)

    command.revision(
        cfg,
        message=message,
        autogenerate=autogenerate,
        head=head,
        branch_label=branch_label,
        version_path=version_path,
        sql=sql,
    )


def upgrade(
        project_root: Path | str,
        *,
        revision_target: str = "head",
) -> None:
    """
    Apply migrations forward.

    Example:
        >>> upgrade("..")          # to head
        >>> upgrade("..", "base")  # or to a specific rev
    """
    database_url = get_database_url_from_env(required=True)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)
    command.upgrade(cfg, revision_target)


def downgrade(
        project_root: Path | str,
        *,
        revision_target: str = "-1",
) -> None:
    """Revert migrations down to the specified revision or relative step.

    Args:
        project_root: Directory containing alembic.ini and migrations/.
        revision_target: Target revision identifier or relative step (e.g. "-1").
    """
    database_url = get_database_url_from_env(required=True)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)
    command.downgrade(cfg, revision_target)


def current(
        project_root: Path | str,
        *,
        verbose: bool = False,
) -> None:
    """Print the current database revision(s)."""
    database_url = get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)
    command.current(cfg, verbose=verbose)


def history(
        project_root: Path | str,
        *,
        verbose: bool = False,
) -> None:
    """Show the migration history for this project."""
    database_url = get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)
    command.history(cfg, verbose=verbose)


def stamp(
        project_root: Path | str,
        *,
        revision_target: str = "head",
) -> None:
    """Set the current database revision without running migrations. Useful for marking an existing database as up-to-date."""
    database_url = get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    repair_alembic_state_if_needed(cfg)
    command.stamp(cfg, revision_target)


def merge_heads(
        project_root: Path | str,
        *,
        message: Optional[str] = None,
) -> None:
    """Create a merge revision that joins multiple migration heads."""
    database_url = get_database_url_from_env(required=False)
    root = _prepare_env(project_root, database_url=database_url)
    cfg = build_alembic_config(root)
    command.merge(cfg, "heads", message=message)


# ---------- High-level convenience API ----------

@dataclass(frozen=True)
class SetupAndMigrateResult:
    """Structured outcome of setup_and_migrate."""
    project_root: Path
    migrations_dir: Path
    alembic_ini: Path
    created_initial_revision: bool
    created_followup_revision: bool
    upgraded: bool

    def to_dict(self) -> dict:
        return {
            "project_root": str(self.project_root),
            "migrations_dir": str(self.migrations_dir),
            "alembic_ini": str(self.alembic_ini),
            "created_initial_revision": self.created_initial_revision,
            "created_followup_revision": self.created_followup_revision,
            "upgraded": self.upgraded,
        }

def setup_and_migrate(
        *,
        project_root: Path | str,
        overwrite_scaffold: bool = False,
        create_db_if_missing: bool = True,
        create_followup_revision: bool = True,
        initial_message: str = "initial schema",
        followup_message: str = "autogen",
        return_dict: bool = True,
        database_url: str = None,
) -> SetupAndMigrateResult:
    """
    Ensure DB + Alembic are ready and up-to-date.

    Auto-detects async vs. sync from DATABASE_URL.
    """
    root = _prepare_env(project_root, database_url=database_url)

    if create_db_if_missing:
        ensure_database_exists(database_url)

    # Auto-detect async from the URL (kept for parity; not used directly here)
    from sqlalchemy.engine import make_url as _make_url
    _ = is_async_url(_make_url(database_url))

    mig_dir = init_alembic(
        root,
        discover_packages=None,   # rely on auto-discovery only
        overwrite=overwrite_scaffold,
        database_url=database_url,
    )
    versions_dir = mig_dir / "versions"
    alembic_ini = root / "alembic.ini"

    cfg = build_alembic_config(project_root=root)
    repair_alembic_state_if_needed(cfg)

    created_initial = False
    created_followup = False
    upgraded = False

    try:
        upgrade(root)   # safe if nothing to do
        upgraded = True
    except Exception:
        pass

    def _has_revisions() -> bool:
        return any(versions_dir.glob("*.py"))

    if not _has_revisions():
        revision(
            project_root=root,
            message=initial_message,
            autogenerate=True,
            ensure_head_before_autogenerate=True,
        )
        created_initial = True
        upgrade(root)
        upgraded = True
    elif create_followup_revision:
        revision(
            project_root=root,
            message=followup_message,
            autogenerate=True,
            ensure_head_before_autogenerate=True,
        )
        created_followup = True
        upgrade(root)
        upgraded = True

    result = SetupAndMigrateResult(
        project_root=root,
        migrations_dir=mig_dir,
        alembic_ini=alembic_ini,
        created_initial_revision=created_initial,
        created_followup_revision=created_followup,
        upgraded=upgraded,
    )
    return result.to_dict() if return_dict else result


__all__ = [
    # env helpers
    "get_database_url_from_env",
    "is_async_url",
    # engines and db bootstrap
    "build_engine",
    "ensure_database_exists",
    # alembic init and commands
    "init_alembic",
    "revision",
    "upgrade",
    "downgrade",
    "current",
    "history",
    "stamp",
    "merge_heads",
    # high-level
    "setup_and_migrate",
    "SetupAndMigrateResult",
]