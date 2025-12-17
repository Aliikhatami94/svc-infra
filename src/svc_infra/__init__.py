"""svc-infra: Service Infrastructure Toolkit.

A comprehensive backend infrastructure library providing:
- API framework (FastAPI scaffolding, dual routers, auth)
- Database (SQL/Mongo, migrations, repositories)
- Caching (Redis, decorators)
- Jobs (background tasks, queues)
- Webhooks (delivery, subscriptions)
- Billing (Stripe/Adyen integration)
- Observability (logging, metrics)

Example:
    from svc_infra.api.fastapi import easy_service_app
    from svc_infra.api.fastapi.auth import add_auth_users

    app = easy_service_app(name="MyAPI")
    add_auth_users(app)
"""

from __future__ import annotations

# Core modules (lazy import pattern for optional dependencies)
from . import api, app, cache, db, jobs, webhooks

# Base exception
from .exceptions import SvcInfraError

# Content Loaders
from .loaders import (
    BaseLoader,
    GitHubLoader,
    LoadedContent,
    URLLoader,
    load_github,
    load_github_sync,
    load_url,
    load_url_sync,
)

__all__ = [
    # Core modules
    "api",
    "app",
    "cache",
    "db",
    "jobs",
    "webhooks",
    # Base exception
    "SvcInfraError",
    # Loaders
    "BaseLoader",
    "GitHubLoader",
    "LoadedContent",
    "URLLoader",
    "load_github",
    "load_github_sync",
    "load_url",
    "load_url_sync",
]
