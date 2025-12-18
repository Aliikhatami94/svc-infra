"""Models package - imports all models to register them with SQLAlchemy metadata."""

# Import all models to ensure they're registered with ModelBase.metadata
# CRITICAL: Import order matters for foreign key resolution!
# Base models without dependencies must be imported first.

# 3. Import application models
from svc_infra_template.models.project import Project
from svc_infra_template.models.task import Task

# 2. Import models that depend on User/Organization
# 1. Import User and Organization first (they have no foreign key dependencies to other models)
from svc_infra_template.models.user import (
    AuthSession,  # FK to User
    FailedAuthAttempt,  # FK to User
    Organization,
    OrganizationInvitation,  # FK to Organization, User
    OrganizationMembership,  # FK to Organization, User
    ProviderAccount,  # FK to User
    RefreshToken,  # FK to AuthSession
    RefreshTokenRevocation,
    RolePermission,
    Team,  # FK to Organization
    User,
)

__all__ = [
    "User",
    "Organization",
    "AuthSession",
    "RefreshToken",
    "RefreshTokenRevocation",
    "FailedAuthAttempt",
    "ProviderAccount",
    "OrganizationMembership",
    "OrganizationInvitation",
    "Team",
    "RolePermission",
    "Project",
    "Task",
]
