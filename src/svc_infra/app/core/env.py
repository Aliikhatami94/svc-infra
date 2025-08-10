from __future__ import annotations

import os
import warnings
from enum import StrEnum
from functools import cache
from typing import NamedTuple


class Env(StrEnum):
    LOCAL = "local"
    DEV   = "dev"
    TEST  = "test"
    PROD  = "prod"


# Map common aliases -> canonical
SYNONYMS: dict[str, Env] = {
    "development": Env.DEV,
    "dev": Env.DEV,
    "local": Env.LOCAL,
    "test": Env.TEST,
    "preview": Env.TEST,
    "prod": Env.PROD,
    "production": Env.PROD,
}


def _normalize(raw: str | None) -> Env | None:
    if not raw:
        return None
    val = raw.strip().lower()
    if val in (e.value for e in Env):
        return Env(val)  # exact match
    return SYNONYMS.get(val)


@cache
def get_env() -> Env:
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
        env = Env.LOCAL
    return env


class EnvFlags(NamedTuple):
    env: Env
    is_local: bool
    is_dev: bool
    is_test: bool
    is_prod: bool


def get_env_flags(env: Env | None = None) -> EnvFlags:
    e = env or get_env()
    return EnvFlags(
        env=e,
        is_local=(e == Env.LOCAL),
        is_dev=(e == Env.DEV),
        is_test=(e == Env.TEST),
        is_prod=(e == Env.PROD),
    )


# Handy accessors (mirror your previous globals)
ENV: Env = get_env()
FLAGS: EnvFlags = get_env_flags(ENV)
IS_LOCAL, IS_DEV, IS_TEST, IS_PROD = FLAGS.is_local, FLAGS.is_dev, FLAGS.is_test, FLAGS.is_prod


# Small helper you’ll use a lot (e.g., for router exclusions, config picking, etc.)
def pick(*, prod, nonprod, dev=None, test=None, local=None):
    """
    Choose a value based on the active environment.

    Example:
        log_level = pick(prod="INFO", nonprod="DEBUG", dev="DEBUG")
    """
    e = get_env()
    if e is Env.PROD:
        return prod
    if e is Env.DEV and dev is not None:
        return dev
    if e is Env.TEST and test is not None:
        return test
    if e is Env.LOCAL and local is not None:
        return local
    return nonprod