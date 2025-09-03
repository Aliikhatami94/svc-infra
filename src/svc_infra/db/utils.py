import re
from typing import Optional

_ENV_NAME_RE = re.compile(r"^\$?[A-Z_][A-Z0-9_]*$")

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
    - If an ENV name like 'DATABASE_URL' or '$DATABASE_URL' or None -> write empty string,
      and let env.py override from os.getenv at runtime.
    """
    if not database_url:
        return ""
    # If it's an ENV var name, don't write it literally in ini
    if _ENV_NAME_RE.fullmatch(database_url):
        return ""
    return database_url