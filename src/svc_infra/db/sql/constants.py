from __future__ import annotations

import re
from typing import Sequence

# Environment variable names to look up for DB URL
DEFAULT_DB_ENV_VARS: Sequence[str] = (
    "SQL_URL",
    "DB_URL",
)

# Regex used to detect async drivers from URL drivername
ASYNC_DRIVER_HINT = re.compile(r"\+(?:async|asyncpg|aiosqlite|aiomysql|asyncmy|aio\w+)")

# Alembic templates loaded from package resources (svc_infra.db.sql.templates.setup)
# Kept as module-level constants for compatibility with verify.py
try:
    import importlib.resources as pkg

    _tmpl_pkg = pkg.files("svc_infra.db.sql.templates.setup")
    ALEMBIC_INI_TEMPLATE = _tmpl_pkg.joinpath("alembic.ini.tmpl").read_text(encoding="utf-8")
    ALEMBIC_SCRIPT_TEMPLATE = _tmpl_pkg.joinpath("script.py.mako.tmpl").read_text(encoding="utf-8")
except Exception:
    # Fallbacks (should not normally happen). Provide minimal safe defaults.
    ALEMBIC_INI_TEMPLATE = (
        """[alembic]\nscript_location = {script_location}\nsqlalchemy.url = {sqlalchemy_url}\n"""
    )
    ALEMBIC_INI_TEMPLATE = (
        """[alembic]\nscript_location = {script_location}\nsqlalchemy.url = {sqlalchemy_url}\n"""
    )
    ALEMBIC_SCRIPT_TEMPLATE = '"""${message}"""\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision = ${repr(up_revision)}\ndown_revision = ${repr(down_revision)}\nbranch_labels = ${repr(branch_labels)}\ndepends_on = ${repr(depends_on)}\n\ndef upgrade():\n    ${upgrades if upgrades else "pass"}\n\n\ndef downgrade():\n    ${downgrades if downgrades else "pass"}\n'
__all__ = [
    "DEFAULT_DB_ENV_VARS",
    "ASYNC_DRIVER_HINT",
    "ALEMBIC_INI_TEMPLATE",
    "ALEMBIC_SCRIPT_TEMPLATE",
]
