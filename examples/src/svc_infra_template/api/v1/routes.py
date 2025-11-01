"""API v1 routes."""

from fastapi import APIRouter

router = APIRouter()


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
