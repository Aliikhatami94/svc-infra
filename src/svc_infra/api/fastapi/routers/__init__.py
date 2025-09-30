from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType
from typing import Optional

from fastapi import FastAPI
from fastapi.routing import APIRoute

from svc_infra.app.env import ALL_ENVIRONMENTS, CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV, Environment

logger = logging.getLogger(__name__)


def _should_skip_module(module_name: str) -> bool:
    """
    Returns True if the module should be skipped based on:
    - private/dunder final segment
    """
    parts = module_name.split(".")
    last_segment = parts[-1]
    return last_segment.startswith("_")


def _derive_docs_from_module(module: ModuleType) -> tuple[str | None, str | None]:
    # 1) explicit constants win
    mod_summary = getattr(module, "ROUTER_SUMMARY", None)
    mod_description = getattr(module, "ROUTER_DESCRIPTION", None)
    if mod_summary or mod_description:
        return mod_summary, mod_description

    # 2) fallback: module docstring (first non-empty line = summary; rest = description)
    doc = (module.__doc__ or "").strip()
    if not doc:
        return None, None
    lines = [ln.strip() for ln in doc.splitlines()]
    lines = [ln for ln in lines if ln]  # drop empties
    if not lines:
        return None, None
    summary = lines[0]
    description = "\n".join(lines[1:]) if len(lines) > 1 else None
    return summary, description


def _validate_base_package(base_package: str) -> ModuleType:
    """Validate and import the base package."""
    try:
        package_module: ModuleType = importlib.import_module(base_package)
    except Exception as exc:
        raise RuntimeError(f"Could not import base_package '{base_package}': {exc}") from exc

    if not hasattr(package_module, "__path__"):
        raise RuntimeError(
            f"Provided base_package '{base_package}' is not a package (no __path__)."
        )

    return package_module


def _normalize_environment(environment: Optional[Environment | str]) -> Environment:
    """Normalize the environment parameter."""
    return (
        CURRENT_ENVIRONMENT
        if environment is None
        else (Environment(environment) if not isinstance(environment, Environment) else environment)
    )


def _should_force_include_in_schema(
    environment: Environment, force_include_in_schema: Optional[bool]
) -> bool:
    """Determine if routers should be forced to include in schema."""
    if force_include_in_schema is None:
        return environment in (LOCAL_ENV, DEV_ENV)
    return force_include_in_schema


def _is_router_excluded_by_environment(
    module: ModuleType, environment: Environment, module_name: str
) -> bool:
    """Check if router should be excluded based on environment restrictions."""
    router_excluded_envs = getattr(module, "ROUTER_EXCLUDED_ENVIRONMENTS", None)
    if router_excluded_envs is None:
        return False

    # Support ALL_ENVIRONMENTS as a special value
    if router_excluded_envs is ALL_ENVIRONMENTS or (
        isinstance(router_excluded_envs, set) and router_excluded_envs == ALL_ENVIRONMENTS
    ):
        logger.debug(f"Skipping router module {module_name} due to ALL_ENVIRONMENTS exclusion.")
        return True

    # Normalize to set of Environment or str
    if not isinstance(router_excluded_envs, (set, list, tuple)):
        logger.warning(
            f"ROUTER_EXCLUDED_ENVIRONMENTS in {module_name} must be a set/list/tuple, got {type(router_excluded_envs)}"
        )
        return False

    normalized_excluded_envs = set()
    for e in router_excluded_envs:
        try:
            normalized_excluded_envs.add(Environment(e) if not isinstance(e, Environment) else e)
        except Exception:
            normalized_excluded_envs.add(str(e))

    if environment in normalized_excluded_envs or str(environment) in normalized_excluded_envs:
        logger.debug(
            f"Skipping router module {module_name} due to ROUTER_EXCLUDED_ENVIRONMENTS restriction: {router_excluded_envs}"
        )
        return True

    return False


def _is_router_included_by_environment(
    module: ModuleType, environment: Environment, module_name: str
) -> bool:
    router_envs = getattr(module, "ROUTER_ENVIRONMENTS", None)
    if router_envs is None:
        return True
    if not isinstance(router_envs, (set, list, tuple)):
        logger.warning(
            f"ROUTER_ENVIRONMENTS in {module_name} must be a set/list/tuple, got {type(router_envs)}"
        )
        return True
    normalized = set()
    for e in router_envs:
        try:
            normalized.add(Environment(e) if not isinstance(e, Environment) else e)
        except Exception:
            normalized.add(str(e))
    inc = environment in normalized or str(environment) in normalized
    if not inc:
        logger.debug(
            f"Skipping router module {module_name} due to ROUTER_ENVIRONMENTS restriction: {router_envs}"
        )
    return inc


def _should_never_include_in_schema(module: ModuleType) -> bool:
    """Check if router should never be included in schema."""
    return getattr(module, "ROUTER_NEVER_IN_SCHEMA", False) is True


def _apply_default_docs_to_routes(
    router, default_summary: str | None, default_description: str | None
) -> None:
    """Apply default summary and description to routes that don't have them."""
    for r in getattr(router, "routes", []):
        if isinstance(r, APIRoute):
            if not r.summary and default_summary:
                r.summary = default_summary
            if not r.description and default_description:
                r.description = default_description


def _build_include_kwargs(module: ModuleType, prefix: str, force_include: bool) -> dict:
    """Build the kwargs for app.include_router."""
    router_prefix = getattr(module, "ROUTER_PREFIX", None)
    router_tag = getattr(module, "ROUTER_TAG", None)
    include_in_schema = getattr(module, "INCLUDE_ROUTER_IN_SCHEMA", True)

    include_kwargs = {"prefix": prefix}
    if router_prefix:
        include_kwargs["prefix"] = prefix.rstrip("/") + router_prefix
    if router_tag:
        include_kwargs["tags"] = [router_tag]

    # the key line: force in LOCAL, otherwise respect the module
    include_kwargs["include_in_schema"] = True if force_include else include_in_schema

    return include_kwargs


def _process_router_module(
    app: FastAPI,
    module: ModuleType,
    module_name: str,
    prefix: str,
    environment: Environment,
    force_include: bool,
) -> bool:
    router = getattr(module, "router", None)
    if router is None:
        return False

    if _is_router_excluded_by_environment(module, environment, module_name):
        return False
    if not _is_router_included_by_environment(module, environment, module_name):
        return False
    if _should_never_include_in_schema(module):
        return False

    app.include_router(
        router,
        prefix=prefix,
        include_in_schema=True if force_include else router.include_in_schema,
    )
    return True


def register_all_routers(
    app: FastAPI,
    *,
    base_package: Optional[str] = None,
    prefix: str = "",
    environment: Optional[Environment | str] = None,
    force_include_in_schema: Optional[bool] = None,
) -> None:
    """
    Recursively discover and register all FastAPI routers under a routers package.

    Args:
        app: FastAPI application instance.
        base_package: Import path to the root routers package (e.g., "myapp.api.routers").
            If omitted, derived from this module's package.
        prefix: API prefix for all routers (e.g., "/v0").
        environment: The current environment (defaults to get_env()).

    Behavior:
        - Any module under the package with a top-level `router` variable is included.
        - Files/packages whose final segment starts with '_' are skipped.
        - If a module defines ROUTER_ENVIRONMENTS, it is a set/list of environments (Env or str) in which the router is included.
        - Import errors are logged and skipped.
        - Nested discovery requires `__init__.py` files in packages.
        - If a module defines ROUTER_PREFIX or ROUTER_TAGS, they are used for that router.
    """
    if base_package is None:
        if __package__ is None:
            raise RuntimeError("Cannot derive base_package; please pass base_package explicitly.")
        base_package = __package__

    package_module = _validate_base_package(base_package)
    environment = _normalize_environment(environment)
    force_include = _should_force_include_in_schema(environment, force_include_in_schema)

    for _, module_name, _ in pkgutil.walk_packages(
        package_module.__path__, prefix=f"{base_package}."
    ):
        if _should_skip_module(module_name):
            logger.debug("Skipping router module due to exclusion/private: %s", module_name)
            continue

        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.exception("Failed to import router module %s: %s", module_name, exc)
            continue

        _process_router_module(app, module, module_name, prefix, environment, force_include)
