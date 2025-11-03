"""
REFERENCE IMPLEMENTATION: Authentication with svc-infra

This file demonstrates how to properly wire authentication using add_auth_users().
It serves as a working example that users can copy from after running scaffold_models.py.

This implementation shows:
1. How to define a User model that works with fastapi-users
2. How to create Pydantic schemas for User operations
3. How to properly call add_auth_users() with all required parameters
4. What auth endpoints become available after wiring

To use this in your template:
1. Run: python scaffold_models.py --user-only
2. Copy the generated models/user.py and schemas/user.py
3. Update main.py to import and use them (see below)
4. Set AUTH_ENABLED=true in .env
5. Start the server and test the auth endpoints

Auth Endpoints Added:
- POST /auth/register          - Register new user
- POST /auth/login             - Login with email/password
- POST /auth/logout            - Logout (clear session)
- GET  /users/me               - Get current authenticated user
- PATCH /users/me              - Update current user
- POST /users/verify           - Verify email with token
- POST /users/forgot-password  - Request password reset
- POST /users/reset-password   - Reset password with token
- GET  /auth/sessions/me       - List active sessions
- DELETE /auth/sessions/{id}   - Revoke a session
- POST /auth/mfa/enable        - Enable MFA/TOTP
- POST /auth/mfa/verify        - Verify MFA code
- POST /auth/api-keys          - Create API key
- GET  /auth/api-keys          - List API keys
- DELETE /auth/api-keys/{id}   - Revoke API key
- GET  /auth/oauth/google/authorize  - OAuth with Google
- GET  /auth/oauth/github/authorize  - OAuth with GitHub
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi_users import schemas

# fastapi-users base models
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

# SQLAlchemy imports
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

# Your app's base
from svc_infra_template.db.base import Base

# ============================================================================
# USER MODEL (SQLAlchemy)
# ============================================================================
# This is what gets scaffolded by: svc-infra sql scaffold --kind auth


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    User model for authentication.

    Inherits from SQLAlchemyBaseUserTableUUID which provides:
    - id: UUID (primary key)
    - email: str (unique, indexed)
    - hashed_password: str
    - is_active: bool
    - is_superuser: bool
    - is_verified: bool

    We add custom fields below for multi-tenancy and soft delete.
    """

    __tablename__ = "users"

    # Multi-tenancy support
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True, comment="Tenant ID for multi-tenancy isolation"
    )

    # Soft delete support
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
    )

    # Add any custom fields here
    # phone_number: Mapped[Optional[str]] = mapped_column(String(20))
    # avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    # bio: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ============================================================================
# USER SCHEMAS (Pydantic)
# ============================================================================
# These are what gets scaffolded by: svc-infra sql scaffold --kind auth


class UserRead(schemas.BaseUser[UUID]):
    """
    Schema for reading user data (returned by API).

    Inherits from BaseUser which provides:
    - id: UUID
    - email: str
    - is_active: bool
    - is_superuser: bool
    - is_verified: bool

    Add custom fields that should be readable.
    """

    tenant_id: Optional[str] = None
    # Add custom readable fields
    # phone_number: Optional[str] = None
    # avatar_url: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    """
    Schema for user registration (input).

    Inherits from BaseUserCreate which provides:
    - email: str
    - password: str
    - is_active: bool (optional, defaults to True)
    - is_superuser: bool (optional, defaults to False)
    - is_verified: bool (optional, defaults to False)

    Add custom fields that can be set during registration.
    """

    tenant_id: Optional[str] = None
    # Add custom creation fields
    # phone_number: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    """
    Schema for updating user data (input).

    Inherits from BaseUserUpdate which provides:
    - email: Optional[str]
    - password: Optional[str]
    - is_active: Optional[bool]
    - is_superuser: Optional[bool]
    - is_verified: Optional[bool]

    All fields are optional for partial updates.
    Add custom fields that can be updated.
    """

    # Add custom updatable fields
    # phone_number: Optional[str] = None
    # avatar_url: Optional[str] = None
    # bio: Optional[str] = None


# ============================================================================
# HOW TO WIRE IN MAIN.PY
# ============================================================================
"""
After generating models with scaffold_models.py, update your main.py:

# At the top of main.py
from svc_infra_template.models.user import User
from svc_infra_template.schemas.user import UserRead, UserCreate, UserUpdate

# In the authentication section (uncomment and update)
if settings.auth_enabled and settings.database_configured:
    from svc_infra.api.fastapi.auth.add import add_auth_users

    add_auth_users(
        app,
        user_model=User,
        schema_read=UserRead,
        schema_create=UserCreate,
        schema_update=UserUpdate,
        enable_password=True,      # Email/password authentication
        enable_oauth=True,          # Google, GitHub OAuth
        enable_api_keys=False,      # Service-to-service API keys
        post_login_redirect="/",    # Where to redirect after OAuth login
    )

    print("✅ Authentication enabled with full user management")

Then in .env:
    AUTH_ENABLED=true
    AUTH_SECRET=your-secret-key-here

    # Optional OAuth configuration
    # AUTH_GOOGLE_CLIENT_ID=...
    # AUTH_GOOGLE_CLIENT_SECRET=...
    # AUTH_GITHUB_CLIENT_ID=...
    # AUTH_GITHUB_CLIENT_SECRET=...

Start server and test:
    make run

    # Register a user
    curl -X POST http://localhost:8001/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email":"user@example.com","password":"securepass123"}'

    # Login
    curl -X POST http://localhost:8001/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"user@example.com","password":"securepass123"}'

    # Get current user (requires session cookie from login)
    curl http://localhost:8001/users/me \
      -H "Cookie: svc_session=<session_from_login>"
"""
