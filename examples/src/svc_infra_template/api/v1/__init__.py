"""API v1 package."""

from fastapi import APIRouter

from . import routes

# Create the main v1 router
router = APIRouter()

# Include all route modules
router.include_router(routes.router, tags=["General"])

__all__ = ["router"]
