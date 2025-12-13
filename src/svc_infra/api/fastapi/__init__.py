from svc_infra.api.fastapi.dual import (
    DualAPIRouter,
    dualize_protected,
    dualize_public,
    dualize_user,
)
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.health import (
    add_dependency_health,
    add_health_routes,
    add_startup_probe,
    check_database,
    check_redis,
    check_url,
)

from .cache.add import setup_caching
from .ease import easy_service_api, easy_service_app
from .pagination import cursor_window, sort_by, text_filter, use_pagination
from .setup import setup_service_api

__all__ = [
    "DualAPIRouter",
    "dualize_public",
    "dualize_user",
    "dualize_protected",
    "ServiceInfo",
    "APIVersionSpec",
    # Health
    "add_startup_probe",
    "add_health_routes",
    "add_dependency_health",
    "check_database",
    "check_redis",
    "check_url",
    # Ease
    "setup_service_api",
    "easy_service_api",
    "easy_service_app",
    "setup_caching",
    # Pagination
    "use_pagination",
    "text_filter",
    "sort_by",
    "cursor_window",
]
