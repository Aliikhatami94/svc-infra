from __future__ import annotations

# Backward-compat shim: expose Alembic helpers from new package
from .alembic.cli import init_migrations, make_migration, upgrade, downgrade  # noqa: F401
from .alembic.env_templates import write_async_env_template  # noqa: F401


def ensure_initted(cwd: str = ".") -> None:  # noqa: D401
    """Ensure Alembic is initialized and env template is written."""
    # Defer import of init_migrations to avoid circulars in some setups
    from pathlib import Path
    import os

    ini_path = Path(cwd) / "alembic.ini"
    if not ini_path.exists():
        init_migrations(cwd)
    write_async_env_template(cwd)
