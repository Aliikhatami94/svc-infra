from __future__ import annotations

import os
import warnings
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import List, NamedTuple, Optional

from dotenv import load_dotenv

from svc_infra.app.root import resolve_project_root


class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


# Handy aliases
LOCAL_ENV = Environment.LOCAL
DEV_ENV = Environment.DEV
TEST_ENV = Environment.TEST
PROD_ENV = Environment.PROD


# Map common aliases -> canonical
SYNONYMS: dict[str, Environment] = {
    "development": DEV_ENV,
    "dev": DEV_ENV,
    "local": LOCAL_ENV,
    "uat": TEST_ENV,
    "test": TEST_ENV,
    "preview": TEST_ENV,
    "staging": TEST_ENV,
    "prod": PROD_ENV,
    "production": PROD_ENV,
}

ALL_ENVIRONMENTS = {e for e in Environment}


def _normalize(raw: str | None) -> Environment | None:
    """
    Normalize raw environment string to canonical Env enum, case-insensitively.
    """
    if not raw:
        return None
    val = raw.strip().casefold()  # case-insensitive, handles unicode edge cases
    # Check against canonical enum values
    if val in (e.value for e in Environment):
        return Environment(val)  # exact match
    # Check against synonyms
    return SYNONYMS.get(val)


@cache
def get_current_environment() -> Environment:
    """
    Resolve the current environment once, with sensible fallbacks.

    Precedence:
      1) APP_ENV
      2) RAILWAY_ENVIRONMENT_NAME
      3) "local" (default)

    Unknown values fall back to LOCAL with a one-time warning.
    """
    raw = os.getenv("APP_ENV") or os.getenv("RAILWAY_ENVIRONMENT_NAME")
    env = _normalize(raw)
    if env is None:
        if raw:
            warnings.warn(
                f"Unrecognized environment '{raw}', defaulting to 'local'.",
                RuntimeWarning,
                stacklevel=2,
            )
        env = LOCAL_ENV
    return env


class EnvironmentFlags(NamedTuple):
    environment: Environment
    is_local: bool
    is_dev: bool
    is_test: bool
    is_prod: bool


def get_environment_flags(environment: Environment | None = None) -> EnvironmentFlags:
    e = environment or get_current_environment()
    return EnvironmentFlags(
        environment=e,
        is_local=(e == _normalize("local")),
        is_dev=(e == _normalize("dev")),
        is_test=(e == _normalize("test")),
        is_prod=(e == _normalize("prod")),
    )


# Handy globals
CURRENT_ENVIRONMENT: Environment = get_current_environment()
ENV_FLAGS: EnvironmentFlags = get_environment_flags(CURRENT_ENVIRONMENT)
IS_LOCAL, IS_DEV, IS_TEST, IS_PROD = (
    ENV_FLAGS.is_local,
    ENV_FLAGS.is_dev,
    ENV_FLAGS.is_test,
    ENV_FLAGS.is_prod,
)


def pick(*, prod, nonprod=None, dev=None, test=None, local=None):
    """
    Choose a value based on the active environment.

    Example:
        log_level = pick(prod="INFO", nonprod="DEBUG", dev="DEBUG")
    """
    e = get_current_environment()
    if e is PROD_ENV:
        return prod
    if e is DEV_ENV and dev is not None:
        return dev
    if e is TEST_ENV and test is not None:
        return test
    if e is LOCAL_ENV and local is not None:
        return local
    if nonprod is not None:
        return nonprod
    raise ValueError("pick(): No value found for environment and 'nonprod' was not provided.")


def find_env_file(start: Optional[Path] = None) -> Optional[Path]:
    env_file = os.getenv("APP_ENV_FILE") or os.getenv("SVC_INFRA_ENV_FILE")
    if env_file:
        p = Path(env_file).expanduser()
        return p if p.exists() else None

    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        candidate = p / ".env"
        if candidate.exists():
            return candidate
    return None


def load_env_if_present(path: Optional[Path], *, override: bool = False) -> List[str]:
    if not path:
        return []
    before = dict(os.environ)
    load_dotenv(dotenv_path=path, override=override)
    changed = []
    for k, v in os.environ.items():
        if k not in before or before.get(k) != v:
            changed.append(k)
    return sorted(changed)


def prepare_env() -> Path:
    """
    Return (project_root, debug_note). No chdir here; runner handles cwd.
    """
    root = resolve_project_root()
    env_file = find_env_file(start=root)
    load_env_if_present(env_file, override=False)
    return root
