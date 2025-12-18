"""PaaS and deployment utilities for svc-infra applications.

This module provides platform detection and environment resolution
utilities for deploying FastAPI applications to various cloud providers,
PaaS platforms, and containerized environments.

Supported platforms:
- **Developer PaaS**: Railway, Render, Fly.io, Heroku
- **AWS**: ECS/Fargate, Lambda, Elastic Beanstalk
- **Google Cloud**: Cloud Run, App Engine, GCE
- **Azure**: Container Apps, Functions, App Service
- **Container**: Kubernetes, Docker, Podman

The goal is to abstract away platform-specific environment variable
naming conventions while allowing full customization.

Example:
    >>> from svc_infra.deploy import get_platform, get_port, get_database_url
    >>>
    >>> # Auto-detect platform
    >>> platform = get_platform()
    >>> print(platform)  # "railway", "aws_ecs", "cloud_run", "local", etc.
    >>>
    >>> # Get port with platform-aware defaults
    >>> port = get_port()  # Reads PORT env var, defaults to 8000
    >>>
    >>> # Get database URL with platform-specific variable resolution
    >>> db_url = get_database_url()  # Handles DATABASE_URL_PRIVATE for Railway
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import cache


class Platform(StrEnum):
    """Detected deployment platform."""

    # Developer PaaS
    RAILWAY = "railway"
    RENDER = "render"
    FLY = "fly"
    HEROKU = "heroku"

    # AWS
    AWS_ECS = "aws_ecs"  # ECS/Fargate
    AWS_LAMBDA = "aws_lambda"
    AWS_BEANSTALK = "aws_beanstalk"

    # Google Cloud
    CLOUD_RUN = "cloud_run"
    APP_ENGINE = "app_engine"
    GCE = "gce"

    # Azure
    AZURE_CONTAINER_APPS = "azure_container_apps"
    AZURE_FUNCTIONS = "azure_functions"
    AZURE_APP_SERVICE = "azure_app_service"

    # Container/Orchestration
    KUBERNETES = "kubernetes"
    DOCKER = "docker"

    # Local development
    LOCAL = "local"


# Platform detection environment variables
# Each platform sets specific env vars we can detect
# Order matters: more specific platforms checked first
PLATFORM_SIGNATURES: dict[Platform, tuple[str, ...]] = {
    # Developer PaaS (most specific first)
    Platform.RAILWAY: (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
    ),
    Platform.RENDER: ("RENDER", "RENDER_SERVICE_ID", "RENDER_INSTANCE_ID"),
    Platform.FLY: ("FLY_APP_NAME", "FLY_REGION", "FLY_ALLOC_ID"),
    Platform.HEROKU: ("DYNO", "HEROKU_APP_NAME", "HEROKU_SLUG_COMMIT"),
    # AWS
    Platform.AWS_LAMBDA: ("AWS_LAMBDA_FUNCTION_NAME", "LAMBDA_TASK_ROOT"),
    Platform.AWS_ECS: ("ECS_CONTAINER_METADATA_URI", "ECS_CONTAINER_METADATA_URI_V4"),
    Platform.AWS_BEANSTALK: ("ELASTIC_BEANSTALK_ENVIRONMENT_NAME",),
    # Google Cloud
    Platform.CLOUD_RUN: ("K_SERVICE", "K_REVISION", "K_CONFIGURATION"),
    Platform.APP_ENGINE: ("GAE_APPLICATION", "GAE_SERVICE", "GAE_VERSION"),
    Platform.GCE: ("GCE_METADATA_HOST",),
    # Azure
    Platform.AZURE_CONTAINER_APPS: (
        "CONTAINER_APP_NAME",
        "CONTAINER_APP_ENV_DNS_SUFFIX",
    ),
    Platform.AZURE_FUNCTIONS: ("FUNCTIONS_WORKER_RUNTIME", "AzureWebJobsStorage"),
    Platform.AZURE_APP_SERVICE: ("WEBSITE_SITE_NAME", "WEBSITE_INSTANCE_ID"),
    # Generic container/orchestration (check last)
    Platform.KUBERNETES: ("KUBERNETES_SERVICE_HOST", "KUBERNETES_PORT"),
    Platform.DOCKER: ("DOCKER_CONTAINER",),  # User must set this; no reliable auto-detect
}

# Container detection paths (Linux-specific)
CONTAINER_MARKERS = (
    "/.dockerenv",
    "/run/.containerenv",  # Podman
)


def _is_in_container() -> bool:
    """
    Detect if running inside a container.

    Uses multiple heuristics:
    1. /.dockerenv file exists (Docker)
    2. /run/.containerenv exists (Podman)
    3. /proc/1/cgroup contains container-related strings
    """
    # Check marker files
    for marker in CONTAINER_MARKERS:
        if os.path.exists(marker):
            return True

    # Check cgroup (Linux)
    try:
        with open("/proc/1/cgroup") as f:
            cgroup = f.read()
            if "docker" in cgroup or "kubepods" in cgroup or "containerd" in cgroup:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


@cache
def get_platform() -> Platform:
    """
    Detect the current deployment platform.

    Detection order:
    1. Check for platform-specific environment variables
    2. Check for container markers
    3. Default to LOCAL

    Returns:
        Platform enum value

    Example:
        >>> platform = get_platform()
        >>> if platform == Platform.RAILWAY:
        ...     # Railway-specific logic
        ...     pass
    """
    # Check each platform's signature env vars
    for platform, env_vars in PLATFORM_SIGNATURES.items():
        for var in env_vars:
            if os.environ.get(var):
                return platform

    # Check for generic container environment
    if _is_in_container():
        return Platform.DOCKER

    return Platform.LOCAL


# Platform category groupings
AWS_PLATFORMS = frozenset({Platform.AWS_ECS, Platform.AWS_LAMBDA, Platform.AWS_BEANSTALK})
GCP_PLATFORMS = frozenset({Platform.CLOUD_RUN, Platform.APP_ENGINE, Platform.GCE})
AZURE_PLATFORMS = frozenset(
    {
        Platform.AZURE_CONTAINER_APPS,
        Platform.AZURE_FUNCTIONS,
        Platform.AZURE_APP_SERVICE,
    }
)
PAAS_PLATFORMS = frozenset({Platform.RAILWAY, Platform.RENDER, Platform.FLY, Platform.HEROKU})


def is_aws() -> bool:
    """Check if running on AWS (ECS, Lambda, Beanstalk)."""
    return get_platform() in AWS_PLATFORMS


def is_gcp() -> bool:
    """Check if running on Google Cloud (Cloud Run, App Engine, GCE)."""
    return get_platform() in GCP_PLATFORMS


def is_azure() -> bool:
    """Check if running on Azure (Container Apps, Functions, App Service)."""
    return get_platform() in AZURE_PLATFORMS


def is_paas() -> bool:
    """Check if running on developer PaaS (Railway, Render, Fly, Heroku)."""
    return get_platform() in PAAS_PLATFORMS


def is_serverless() -> bool:
    """Check if running in serverless environment (Lambda, Cloud Run, Functions)."""
    return get_platform() in {
        Platform.AWS_LAMBDA,
        Platform.CLOUD_RUN,
        Platform.AZURE_FUNCTIONS,
    }


def is_containerized() -> bool:
    """
    Check if running in any containerized environment.

    This includes PaaS platforms (Railway, Render, Fly, Heroku),
    cloud providers (AWS, GCP, Azure), Kubernetes, Docker, etc.

    Returns:
        True if in a container/cloud, False if local

    Example:
        >>> if is_containerized():
        ...     # Enable structured logging, disable debug mode
        ...     pass
    """
    platform = get_platform()
    return platform != Platform.LOCAL


def is_local() -> bool:
    """
    Check if running in local development environment.

    Returns:
        True if local, False if deployed
    """
    return get_platform() == Platform.LOCAL


def get_port(default: int = 8000) -> int:
    """
    Get the HTTP port to bind to.

    All major PaaS platforms set the PORT environment variable.
    Falls back to the provided default for local development.

    Args:
        default: Port to use if PORT is not set (default: 8000)

    Returns:
        Port number as integer

    Example:
        >>> import uvicorn
        >>> uvicorn.run(app, host="0.0.0.0", port=get_port())
    """
    port_str = os.environ.get("PORT", "")
    if port_str.isdigit():
        return int(port_str)
    return default


def get_host(default: str = "127.0.0.1") -> str:
    """
    Get the host address to bind to.

    In containerized environments, binds to 0.0.0.0 to accept
    external connections. Locally, binds to 127.0.0.1 for security.

    Args:
        default: Host to use for local development (default: "127.0.0.1")

    Returns:
        Host address string

    Example:
        >>> import uvicorn
        >>> uvicorn.run(app, host=get_host(), port=get_port())
    """
    if is_containerized():
        return "0.0.0.0"
    return os.environ.get("HOST", default)


def get_database_url(
    *,
    prefer_private: bool = True,
    normalize: bool = True,
) -> str | None:
    """
    Get database URL with platform-aware resolution.

    Handles platform-specific naming conventions:
    - Railway: DATABASE_URL_PRIVATE (internal) vs DATABASE_URL (public)
    - Render: DATABASE_URL (internal service communication)
    - Heroku: DATABASE_URL (with postgres:// that needs normalization)

    Args:
        prefer_private: If True, prefer *_PRIVATE variants for internal
            networking (free egress on Railway). Default: True
        normalize: If True, convert postgres:// to postgresql://
            for SQLAlchemy compatibility. Default: True

    Returns:
        Database URL string or None if not configured

    Example:
        >>> from sqlalchemy import create_engine
        >>> url = get_database_url()
        >>> if url:
        ...     engine = create_engine(url)
    """
    # Railway-specific: prefer private networking for free egress
    if prefer_private:
        url = os.environ.get("DATABASE_URL_PRIVATE")
        if url:
            return _normalize_url(url) if normalize else url

    # Standard DATABASE_URL (all platforms)
    url = os.environ.get("DATABASE_URL")
    if url:
        return _normalize_url(url) if normalize else url

    # Legacy svc-infra names
    for var in ("SQL_URL", "DB_URL", "PRIVATE_SQL_URL"):
        url = os.environ.get(var)
        if url:
            return _normalize_url(url) if normalize else url

    return None


def get_redis_url(*, prefer_private: bool = True) -> str | None:
    """
    Get Redis URL with platform-aware resolution.

    Similar to get_database_url, handles platform-specific naming:
    - Railway: REDIS_URL_PRIVATE vs REDIS_URL
    - Render: REDIS_URL (internal)
    - Generic: REDIS_URL, CACHE_URL

    Args:
        prefer_private: Prefer *_PRIVATE variants for internal networking

    Returns:
        Redis URL string or None if not configured

    Example:
        >>> from redis import Redis
        >>> url = get_redis_url()
        >>> if url:
        ...     redis = Redis.from_url(url)
    """
    if prefer_private:
        url = os.environ.get("REDIS_URL_PRIVATE") or os.environ.get("REDIS_PRIVATE_URL")
        if url:
            return url

    return (
        os.environ.get("REDIS_URL")
        or os.environ.get("CACHE_URL")
        or os.environ.get("UPSTASH_REDIS_REST_URL")
    )


def _normalize_url(url: str) -> str:
    """
    Normalize database URL for SQLAlchemy compatibility.

    - Converts postgres:// to postgresql:// (Heroku/Railway legacy)
    - Converts postgres+asyncpg:// to postgresql+asyncpg://
    """
    if url.startswith("postgres://"):
        return "postgresql://" + url[11:]
    if url.startswith("postgres+"):
        return "postgresql+" + url[9:]
    return url


def get_service_url(
    service_name: str,
    *,
    default_port: int = 8000,
    scheme: str = "http",
) -> str | None:
    """
    Get URL for an internal service by name.

    Checks platform-specific service discovery mechanisms:
    - Railway: <SERVICE>_URL env var
    - Kubernetes: <SERVICE>_SERVICE_HOST + <SERVICE>_SERVICE_PORT
    - Generic: <SERVICE>_URL env var

    Args:
        service_name: Service name (e.g., "api", "worker")
        default_port: Port to use if not discoverable
        scheme: URL scheme (default: "http")

    Returns:
        Service URL or None if not discoverable

    Example:
        >>> worker_url = get_service_url("worker")
        >>> if worker_url:
        ...     httpx.post(f"{worker_url}/jobs", json=job_data)
    """
    name_upper = service_name.upper().replace("-", "_")

    # Direct URL env var (Railway, custom)
    url = os.environ.get(f"{name_upper}_URL")
    if url:
        return url

    # Kubernetes service discovery
    host = os.environ.get(f"{name_upper}_SERVICE_HOST")
    port = os.environ.get(f"{name_upper}_SERVICE_PORT", str(default_port))
    if host:
        return f"{scheme}://{host}:{port}"

    return None


def get_public_url() -> str | None:
    """
    Get the public URL of this service.

    Platform-specific resolution:
    - Railway: RAILWAY_PUBLIC_DOMAIN
    - Render: RENDER_EXTERNAL_URL
    - Fly: FLY_APP_NAME.fly.dev
    - Heroku: APP_URL or <app>.herokuapp.com

    Returns:
        Public HTTPS URL or None if not available
    """
    # Railway
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        return f"https://{domain}"

    # Render
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        return url

    # Fly.io
    app_name = os.environ.get("FLY_APP_NAME")
    if app_name:
        return f"https://{app_name}.fly.dev"

    # Heroku
    url = os.environ.get("APP_URL")
    if url:
        return url
    app_name = os.environ.get("HEROKU_APP_NAME")
    if app_name:
        return f"https://{app_name}.herokuapp.com"

    return None


def get_environment_name() -> str:
    """
    Get the deployment environment name.

    Checks platform-specific environment variables:
    - Railway: RAILWAY_ENVIRONMENT
    - Render: RENDER_SERVICE_TYPE or "production"
    - Fly: FLY_APP_NAME suffix convention
    - Generic: APP_ENV, ENVIRONMENT, ENV

    Returns:
        Environment name (e.g., "production", "staging", "development")
    """
    # Platform-specific
    env = os.environ.get("RAILWAY_ENVIRONMENT")
    if env:
        return env.lower()

    # Render doesn't have environment name, but has IS_PULL_REQUEST
    if os.environ.get("RENDER"):
        if os.environ.get("IS_PULL_REQUEST") == "true":
            return "preview"
        return "production"

    # Generic
    return (
        os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("ENV")
        or "local"
    ).lower()


def is_production() -> bool:
    """Check if running in production environment."""
    env = get_environment_name()
    return env in ("production", "prod")


def is_preview() -> bool:
    """Check if running in a preview/PR environment."""
    env = get_environment_name()
    return env in ("preview", "pr", "pull_request", "staging")


__all__ = [
    # Platform detection
    "Platform",
    "get_platform",
    "is_containerized",
    "is_local",
    # Cloud provider checks
    "is_aws",
    "is_gcp",
    "is_azure",
    "is_paas",
    "is_serverless",
    # Server binding
    "get_port",
    "get_host",
    # Database/Cache URLs
    "get_database_url",
    "get_redis_url",
    # Service discovery
    "get_service_url",
    "get_public_url",
    # Environment
    "get_environment_name",
    "is_production",
    "is_preview",
]
