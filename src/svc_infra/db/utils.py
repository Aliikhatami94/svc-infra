import os
import re
from typing import Optional, Any
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from pathlib import Path

from svc_infra.db.constants import ALEMBIC_INI, AL_EMBIC_DIR, _ENV_NAME_RE, _ENV_NAME_BRACED_RE, _ENV_PLACEHOLDER_RE

def _normalize_discover_arg(discover_packages) -> str | None:
    """
    Accepts: None | bool | str | list[str]
    - None/True  -> infer from project (return None to indicate 'infer')
    - False      -> explicitly disable discovery (return "")
    - "true"/"false" (strings) -> treated like booleans (agent sometimes sends these)
    - str       -> trimmed as-is (CSV)
    - list      -> comma-joined
    """
    if isinstance(discover_packages, str):
        low = discover_packages.strip().lower()
        if low in ("true", "1", "yes"):
            return None
        if low in ("false", "0", "no"):
            return ""
        return discover_packages.strip()

    if discover_packages is None or discover_packages is True:
        return None
    if discover_packages is False:
        return ""
    if isinstance(discover_packages, (list, tuple)):
        return ",".join(x.strip() for x in discover_packages if str(x).strip())
    return str(discover_packages).strip()

def _resolve_ini_url_value(database_url: Optional[str]) -> str:
    """
    For alembic.ini:
    - If a literal URL is passed -> write it.
    - If an ENV name like 'DATABASE_URL', '$DATABASE_URL', or '${DATABASE_URL}' (any case) or None -> write empty string,
      and let env.py override from os.getenv at runtime.
    """
    if not database_url:
        return ""
    s = str(database_url).strip()
    if _ENV_NAME_RE.fullmatch(s) or _ENV_NAME_BRACED_RE.fullmatch(s):
        return ""
    # Also treat lowercase ${database_url} as an env placeholder
    if _ENV_PLACEHOLDER_RE.fullmatch(s):
        return ""
    return s

def _get_env_value_from_name(v: Optional[str]) -> Optional[str]:
    """
    If v looks like an environment variable name or placeholder
    (e.g., DATABASE_URL, $DATABASE_URL, ${DATABASE_URL}, ${database_url}),
    return its value from os.environ (case-sensitive first, then UPPER).
    Otherwise return v (treat as a literal URL).
    """
    if v is None:
        return None
    s = str(v).strip()
    m = _ENV_PLACEHOLDER_RE.match(s)
    if not m:
        # Not an env placeholder -> treat as literal URL string
        return s if s else None

    name = m.group(1)
    # Try exact case first, then UPPER for agent-provided ${database_url}
    return os.getenv(name) or os.getenv(name.upper())

def _ensure_sslmode_required(url: str) -> str:
    """
    If URL is Postgres and has no sslmode, add sslmode=require for common managed hosts.
    No change for non-Postgres URLs.
    """
    if not url:
        return url
    parsed = urlparse(url)
    scheme = parsed.scheme or ""
    if not scheme.startswith("postgres"):
        return url

    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in q:
        # Heuristic: managed PGs often require SSL. Safe to default to require.
        q["sslmode"] = "require"

    new_query = urlencode(q, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

def _normalize_db_url_for_alembic(url: Optional[str]) -> Optional[str]:
    """
    If a URL is async (e.g., postgresql+asyncpg), normalize to sync driver
    for Alembic CLI so autogenerate/upgrade works with psycopg2/pymysql/sqlite.
    Leave None/empty untouched.
    """
    if not url:
        return url
    # Do a light-weight, string-oriented normalization here; env.py also maps again.
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite", 1)
    if url.startswith("mysql+asyncmy"):
        return url.replace("mysql+asyncmy", "mysql+pymysql", 1)
    return url

def _load_dotenv_if_present(project_root) -> None:
    """
    Load .env from the project root if present. No hard dependency on python-dotenv.
    Silently no-op if python-dotenv is not installed.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    from pathlib import Path
    root = Path(project_root).resolve()
    for candidate in (root / ".env", root.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            break

def _project_paths(project_root: Path) -> dict[str, Path]:
    pr = project_root.resolve()
    return {
        "root": pr,
        "alembic_ini": pr / ALEMBIC_INI,
        "env_py": pr / AL_EMBIC_DIR / "env.py",
        "versions_dir": pr / AL_EMBIC_DIR / "versions",
    }

def _ensure_alembic_bootstrap(*, project_root: Path, database_url: Optional[str]) -> None:
    """Idempotently ensure alembic.ini and migrations/env.py exist."""
    paths = _project_paths(project_root)
    if paths["alembic_ini"].exists() and paths["env_py"].exists():
        return
    # Lazy import to avoid circular dependency with core.py
    from importlib import import_module
    db_core = import_module("svc_infra.db.core")
    db_core.db_init_core(
        project_root=project_root,
        database_url=database_url or "DATABASE_URL",
        discover_packages=False,
    )

def _effective_migration_url(project_root: Path, database_url: Optional[str]) -> str:
    """Load .env, resolve env var names, normalize for Alembic (sync driver, sslmode)."""
    _load_dotenv_if_present(project_root)
    eff = _get_env_value_from_name(database_url) if database_url else os.getenv("DATABASE_URL")
    eff = _normalize_db_url_for_alembic(eff) if eff else eff
    if not eff:
        raise RuntimeError("DATABASE_URL is empty or not set.")
    return eff

def _quote_ident(ident: str) -> str:
    # naive but safe enough: double up internal quotes
    return '"' + ident.replace('"', '""') + '"'

def _parse_table_identifier(raw: str) -> tuple[Optional[str], str]:
    """
    Accepts: 'users' or 'public.users' or '"Weird.Schema"."Weird.Table"'.
    Returns (schema|None, table).
    """
    raw = raw.strip()
    if "." not in raw:
        return (None, raw)
    # do not try to fully parse SQL identifiers here; split once
    schema, table = raw.split(".", 1)
    return (schema.strip(), table.strip())

def _table_exists(engine, schema: Optional[str], table: str) -> bool:
    insp = inspect(engine)
    try:
        names = insp.get_table_names(schema=schema)
    except Exception:
        names = insp.get_table_names()
    return table in names

def _connect_engine(url: str):
    # url here is already normalized for sync driver
    eng = create_engine(url, future=True)
    return eng

def _get_heads(script: ScriptDirectory) -> list[str]:
    try:
        return list(script.get_heads())
    except Exception:
        return []

def _repair_self_loop_if_present(project_root: Path) -> dict[str, Any]:
    """
    Scan migrations/versions for a file whose revision == down_revision.
    If found, reset its down_revision to None and return repair info.
    Safe no-op if nothing is broken.
    """
    versions_dir = project_root.resolve() / AL_EMBIC_DIR / "versions"
    if not versions_dir.exists():
        return {"repaired": False, "reason": "no versions dir"}

    pat_rev   = re.compile(r'^\s*revision\s*=\s*[\'"]([0-9a-f]+)[\'"]\s*$', re.M)
    pat_down  = re.compile(r'^\s*down_revision\s*=\s*([^\n]+)$', re.M)

    for p in sorted(versions_dir.glob("*.py")):
        txt = p.read_text(encoding="utf-8")
        m_rev  = pat_rev.search(txt)
        m_down = pat_down.search(txt)
        if not (m_rev and m_down):
            continue
        rev = m_rev.group(1)
        down_line = m_down.group(1).strip()
        # extract literal down_revision value if present
        m_lit = re.match(r'[\'"]([0-9a-f]+)[\'"]', down_line)
        if m_lit and m_lit.group(1) == rev:
            # self-loop — fix to None
            fixed = pat_down.sub('down_revision = None', txt, count=1)
            p.write_text(fixed, encoding="utf-8")
            return {"repaired": True, "file": str(p), "rev": rev}
    return {"repaired": False}