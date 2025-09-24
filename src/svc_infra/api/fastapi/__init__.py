from .auth.add import add_auth
from .auth.sugar import optional_user, public_router, require_roles, require_user
from .cache.add import setup_caching
from .deps import Require
from .dual_router import DualAPIRouter, dualize_router
from .models import APIVersionSpec, ServiceInfo
from .setup import setup_service_api
from .sugar import easy_service_api, easy_service_app

__all__ = [
    "DualAPIRouter",
    "dualize_router",
    "ServiceInfo",
    "APIVersionSpec",
    "Require",
    # Ease
    "setup_service_api",
    "easy_service_api",
    "easy_service_app",
    "setup_caching",
    # Auth
    "add_auth",
    "public_router",
    "optional_user",
    "require_user",
    "require_roles",
]
