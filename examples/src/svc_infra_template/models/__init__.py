"""Models package - imports all models to register them with SQLAlchemy metadata."""

# Import all models to ensure they're registered with ModelBase.metadata
# CRITICAL: Import order matters for foreign key resolution!
# Base models without dependencies must be imported first.

# 3. Import application models
from svc_infra_template.models.project import Project
from svc_infra_template.models.task import Task

# 2. Import models that depend on User/Organization
# 1. Import User and Organization first (they have no foreign key dependencies to other models)
from svc_infra_template.models.user import AuthSession  # FK to User
from svc_infra_template.models.user import FailedAuthAttempt  # FK to User
from svc_infra_template.models.user import OrganizationInvitation  # FK to Organization, User
from svc_infra_template.models.user import OrganizationMembership  # FK to Organization, User
from svc_infra_template.models.user import ProviderAccount  # FK to User
from svc_infra_template.models.user import RefreshToken  # FK to AuthSession
from svc_infra_template.models.user import Team  # FK to Organization
from svc_infra_template.models.user import (
    Organization,
    RefreshTokenRevocation,
    RolePermission,
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
