from svc_infra.api.fastapi.dual import (
    DualAPIRouter,
    dualize_protected,
    dualize_public,
    dualize_user,
)
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo

from .cache.add import setup_caching
from .deps import Require
from .ease import easy_service_api, easy_service_app
from .setup import setup_service_api

__all__ = [
    "DualAPIRouter",
    "dualize_public",
    "dualize_user",
    "dualize_protected",
    "ServiceInfo",
    "APIVersionSpec",
    "Require",
    # Ease
    "setup_service_api",
    "easy_service_api",
    "easy_service_app",
    "setup_caching",
]
