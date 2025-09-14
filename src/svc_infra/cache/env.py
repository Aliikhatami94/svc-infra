from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _read_secret_from_file(path: str) -> Optional[str]:
    try:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def get_cache_url_from_env(required: bool = True, *, env_var: str = "REDIS_URL") -> Optional[str]:
    """
    Resolve the cache connection string (e.g. redis[s]://... or unix socket).
    Search order:
      1) <ENV_VAR> or <ENV_VAR>_FILE pointing at a file
      2) REDIS_URL_FILE conventional secret
      3) /run/secrets/redis_url
      4) fallback to redis://localhost:6379/0 (only if required=False)
    Writes discovered value back to os.environ[env_var].
    """
    load_dotenv(override=False)

    # 1) Direct env or <ENV>_FILE
    val = os.getenv(env_var, "").strip()
    if val:
        if val.startswith("file:"):
            val = val[5:]
        if os.path.isabs(val) and Path(val).exists():
            file_val = _read_secret_from_file(val)
            if file_val:
                os.environ[env_var] = file_val
                return file_val
        os.environ[env_var] = val
        return val

    fp = os.getenv(f"{env_var}_FILE")
    if fp:
        s = _read_secret_from_file(fp)
        if s:
            os.environ[env_var] = s
            return s

    # 2) Conventional secret env
    fp = os.getenv("REDIS_URL_FILE")
    if fp:
        s = _read_secret_from_file(fp)
        if s:
            os.environ[env_var] = s
            return s

    # 3) Docker/K8s default secret mount
    s = _read_secret_from_file("/run/secrets/redis_url")
    if s:
        os.environ[env_var] = s
        return s

    if required:
        raise RuntimeError(
            f"Cache URL not set. Set {env_var} (or {env_var}_FILE), or REDIS_URL_FILE, "
            "or mount /run/secrets/redis_url."
        )

    # 4) fallback for local/dev if allowed
    default = "redis://localhost:6379/0"
    os.environ.setdefault(env_var, default)
    return default
