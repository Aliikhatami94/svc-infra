"""API v1 routes."""

from svc_infra.api.fastapi.dual.public import public_router

# Root API router using svc-infra's public_router
router = public_router()


@router.get("/ping")
async def ping():
    """Health check endpoint."""
    return {"message": "pong", "service": "svc-infra-template"}


@router.get("/status")
async def status():
    """Status endpoint."""
    return {
        "status": "healthy",
        "service": "svc-infra-template",
        "version": "0.1.0",
    }
