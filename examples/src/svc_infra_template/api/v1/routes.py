"""Enhanced API routes (v1) showcasing svc-infra features."""

from fastapi import APIRouter
from svc_infra_template.settings import settings

router = APIRouter()


@router.get("/ping")
async def ping():
    """Health check endpoint."""
    return {
        "message": "pong",
        "service": "svc-infra-template",
        "version": "0.2.0",
    }


@router.get("/status")
async def status():
    """Detailed status endpoint with feature information."""
    return {
        "status": "healthy",
        "service": "svc-infra-template",
        "version": "0.2.0",
        "environment": settings.app_env,
        "features": {
            "database": settings.database_configured,
            "cache": settings.cache_configured,
            "metrics": settings.metrics_enabled,
            "webhooks": settings.webhooks_enabled,
            "payments": settings.payment_provider,
            "rate_limiting": settings.rate_limit_enabled,
            "idempotency": settings.idempotency_enabled,
        },
    }


@router.get("/features")
async def list_features():
    """List all available features and their configuration."""
    return {
        "service": "svc-infra-template",
        "version": "0.2.0",
        "features": {
            "core": {
                "versioned_api": True,
                "health_checks": True,
                "request_id": True,
                "exception_handling": True,
            },
            "database": {
                "enabled": settings.database_configured,
            },
            "cache": {
                "enabled": settings.cache_configured,
            },
            "observability": {
                "metrics": settings.metrics_enabled,
                "metrics_path": settings.metrics_path if settings.metrics_enabled else None,
            },
            "security": {
                "rate_limiting": settings.rate_limit_enabled,
                "idempotency": settings.idempotency_enabled,
                "cors": settings.cors_enabled,
            },
            "integrations": {
                "payments": settings.payment_provider,
                "webhooks": settings.webhooks_enabled,
            },
            "operations": {
                "maintenance_mode": settings.maintenance_mode,
                "admin": settings.admin_enabled,
                "jobs": settings.jobs_enabled,
            },
        },
        "documentation": {
            "openapi": "/openapi.json",
            "swagger_ui": "/docs",
            "redoc": "/redoc",
        },
    }
