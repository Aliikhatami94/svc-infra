from __future__ import annotations

import os
import warnings
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import NamedTuple

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

ALL_ENVIRONMENTS = set(Environment)


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


def find_env_file(start: Path | None = None) -> Path | None:
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


def load_env_if_present(path: Path | None, *, override: bool = False) -> list[str]:
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


class MissingSecretError(RuntimeError):
    """Raised when a required secret is not configured in production/staging."""

    pass


def require_secret(
    value: str | None,
    name: str,
    *,
    dev_default: str | None = None,
    environments: tuple[str, ...] = ("prod", "production", "staging", "test"),
) -> str:
    """Require a secret to be set in production environments.

    In development/local environments, falls back to dev_default if provided.
    In production environments, raises MissingSecretError if not set.

    Args:
        value: The secret value (may be None or empty)
        name: Name of the secret for error messages (e.g., "SESSION_SECRET")
        dev_default: Default value to use in development (NEVER in production)
        environments: Environments where the secret is required

    Returns:
        The secret value

    Raises:
        MissingSecretError: If secret is not set in production environments

    Example:
        >>> secret = require_secret(
        ...     os.getenv("SESSION_SECRET"),
        ...     "SESSION_SECRET",
        ...     dev_default="dev-only-secret",
        ... )
    """
    if value:
        return value

    current_env = get_current_environment()

    # Check if we're in a production-like environment
    raw_env = os.getenv("APP_ENV") or os.getenv("RAILWAY_ENVIRONMENT_NAME") or ""
    is_production_like = (
        current_env == PROD_ENV
        or current_env == TEST_ENV  # staging/preview
        or raw_env.lower() in environments
    )

    if is_production_like:
        raise MissingSecretError(
            f"SECURITY ERROR: {name} must be set in production/staging environments. "
            f"Current environment: {current_env} (raw: {raw_env!r})"
        )

    # In development, use the dev default if provided
    if dev_default is not None:
        return dev_default

    raise MissingSecretError(
        f"{name} is not set and no dev_default was provided. "
        "Either set the environment variable or provide a dev_default."
    )
