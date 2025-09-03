import re
from typing import Optional

def _normalize_discover_arg(discover_packages) -> str | None:
    """
    Accepts: None | bool | str | list[str]
    - True  -> infer from project (default roots)
    - False -> no discovery (empty)
    - str   -> returned as-is (comma-separated)
    - list  -> comma-joined
    - None  -> infer from project (default roots)
    """
    if discover_packages is None or discover_packages is True:
        return None  # signal "infer"
    if discover_packages is False:
        return ""    # explicitly empty
    if isinstance(discover_packages, (list, tuple)):
        return ",".join(x.strip() for x in discover_packages if str(x).strip())
    return str(discover_packages).strip()


_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

def _resolve_ini_url_value(database_url: Optional[str]) -> str:
    """
    - If database_url is a literal URL → return it as-is for ini.
    - If it's an env var name like 'DATABASE_URL' or None → return empty string
      and let env.py override from os.getenv at runtime.
    """
    if not database_url:
        return ""
    # treat single ALLCAPS token as env var name, not a URL
    if _ENV_NAME_RE.fullmatch(database_url):
        return ""
    return database_url