from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv

from .constants import DEFAULT_MONGO_DB_ENV_VARS, DEFAULT_MONGO_ENV_VARS


def prepare_process_env(project_root: Path | str) -> Path:
    """
    Prepare process environment (dotenv + PYTHONPATH) for code generation/tasks.
    Mirrors the SQL helper but does not touch SQL_URL.
    """
    root = Path(project_root).resolve()
    load_dotenv(dotenv_path=root / ".env", override=False)
    os.environ.setdefault("SKIP_APP_INIT", "1")

    # Make <project>/src importable (src-layout projects)
    src_dir = root / "src"
    if src_dir.exists():
        sys_path = os.environ.get("PYTHONPATH", "")
        parts = [str(src_dir)] + ([sys_path] if sys_path else [])
        os.environ["PYTHONPATH"] = os.pathsep.join(parts)
    return root


def _read_secret_from_file(path: str) -> Optional[str]:
    try:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def get_mongo_url_from_env(
    required: bool = True,
    env_vars: Sequence[str] = DEFAULT_MONGO_ENV_VARS,
) -> Optional[str]:
    """
    Resolve the Mongo connection string with support for:
      - Primary env vars (DEFAULT_MONGO_ENV_VARS).
      - Companion *_FILE secret envs.
      - Conventional secret file path env MONGO_URL_FILE.
      - Default docker mounts: /run/secrets/mongo_url
    When found, writes it into os.environ["MONGO_URL"].
    """
    load_dotenv(override=False)

    # 1) direct envs (and allow absolute file pointers)
    for key in env_vars:
        val = os.getenv(key)
        if val and val.strip():
            s = val.strip()
            if s.startswith("file:"):
                s = s[5:]
            if os.path.isabs(s) and Path(s).exists():
                file_val = _read_secret_from_file(s)
                if file_val:
                    os.environ["MONGO_URL"] = file_val
                    return file_val
            os.environ["MONGO_URL"] = s
            return s

        file_key = f"{key}_FILE"
        file_path = os.getenv(file_key)
        if file_path:
            file_val = _read_secret_from_file(file_path)
            if file_val:
                os.environ["MONGO_URL"] = file_val
                return file_val

    # 2) conventional secret env
    fp = os.getenv("MONGO_URL_FILE")
    if fp:
        file_val = _read_secret_from_file(fp)
        if file_val:
            os.environ["MONGO_URL"] = file_val
            return file_val

    # 3) docker/k8s default secret mount
    file_val = _read_secret_from_file("/run/secrets/mongo_url")
    if file_val:
        os.environ["MONGO_URL"] = file_val
        return file_val

    if required:
        raise RuntimeError(
            "Mongo URL not set. Set MONGO_URL (or MONGODB_URL) or provide *_FILE secret."
        )
    return None


def get_mongo_dbname_from_env(
    required: bool = False,
    env_vars: Sequence[str] = DEFAULT_MONGO_DB_ENV_VARS,
    default: str = "app",
) -> Optional[str]:
    """Return a database name from env; optional (Motor can connect without it)."""
    load_dotenv(override=False)
    for key in env_vars:
        val = os.getenv(key)
        if val and val.strip():
            os.environ["MONGO_DB"] = val.strip()
            return val.strip()
    if required:
        raise RuntimeError("Mongo DB name not set. Set MONGO_DB.")
    return os.getenv("MONGO_DB") or None
