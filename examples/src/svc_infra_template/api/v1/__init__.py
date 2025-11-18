"""API v1 package."""

from svc_infra.api.fastapi.dual.public import public_router

from . import routes

# Create the main v1 router using svc-infra's public_router
router = public_router()

# Include all route modules
router.include_router(routes.router, tags=["General"])

__all__ = ["router"]
