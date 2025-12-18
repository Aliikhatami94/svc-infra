"""svc-infra API module.

Re-exports key API utilities from svc_infra.api.fastapi for convenient imports.
"""

from __future__ import annotations

# Re-export from fastapi submodule
from svc_infra.api.fastapi import (
    APIVersionSpec,
    # Dual routers
    DualAPIRouter,
    # Service setup
    ServiceInfo,
    add_dependency_health,
    add_health_routes,
    # Health checks
    add_startup_probe,
    check_database,
    check_redis,
    check_url,
    cursor_window,
    dualize_protected,
    dualize_public,
    dualize_user,
    easy_service_api,
    easy_service_app,
    setup_caching,
    setup_service_api,
    sort_by,
    text_filter,
    # Pagination
    use_pagination,
)

__all__ = [
    # Dual routers
    "DualAPIRouter",
    "dualize_protected",
    "dualize_public",
    "dualize_user",
    # Service setup
    "ServiceInfo",
    "APIVersionSpec",
    "setup_service_api",
    "easy_service_api",
    "easy_service_app",
    "setup_caching",
    # Health checks
    "add_startup_probe",
    "add_health_routes",
    "add_dependency_health",
    "check_database",
    "check_redis",
    "check_url",
    # Pagination
    "use_pagination",
    "text_filter",
    "sort_by",
    "cursor_window",
]
