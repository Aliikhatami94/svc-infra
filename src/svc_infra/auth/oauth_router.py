from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from fastapi_users.authentication import JWTStrategy
from fastapi_users.password import PasswordHelper

from svc_infra.api.fastapi.db.integration import SessionDep
from .settings import get_auth_settings


def oauth_router(
    user_model: type,
    jwt_strategy: JWTStrategy,
    post_login_redirect: str = "/",
    prefix: str = "/auth/oauth",
) -> APIRouter:
    """Create an OAuth router for Google/GitHub based on environment settings.

    Args:
        user_model: SQLAlchemy model class for your User table.
        jwt_strategy: A configured JWTStrategy instance.
        post_login_redirect: Where to redirect after successful OAuth login (?token=...).
        prefix: Router prefix.
    """
    settings = get_auth_settings()
    oauth = OAuth()

    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            "google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    if settings.github_client_id and settings.github_client_secret:
        oauth.register(
            "github",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret.get_secret_value(),
            authorize_url="https://github.com/login/oauth/authorize",
            access_token_url="https://github.com/login/oauth/access_token",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "user:email"},
        )

    r = APIRouter(prefix=prefix, tags=["auth:oauth"])

    @r.get("/{provider}/login")
    async def oauth_login(request: Request, provider: str):
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")
        redirect_uri = request.url_for("oauth_callback", provider=provider)
        return await client.authorize_redirect(request, str(redirect_uri))

    @r.get("/{provider}/callback", name="oauth_callback")
    async def oauth_callback(request: Request, provider: str, session: SessionDep):
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        token = await client.authorize_access_token(request)

        if provider == "google":
            userinfo = token.get("userinfo") or await client.parse_id_token(request, token)
            email = userinfo.get("email")
            full_name = userinfo.get("name")
        elif provider == "github":
            resp = await client.get("user", token=token)
            data = resp.json()
            email = data.get("email")
            if not email:
                emails = (await client.get("user/emails", token=token)).json()
                primary = next((e for e in emails if e.get("primary")), emails[0] if emails else {})
                email = primary.get("email")
            full_name = data.get("name")
        else:
            raise HTTPException(400, "Unsupported provider")

        if not email:
            raise HTTPException(400, "No email from provider")

        # Find or create user by email
        from sqlalchemy.ext.asyncio import AsyncSession  # for type checkers
        existing = (await session.execute(select(user_model).filter_by(email=email))).scalars().first()
        if existing:
            user = existing
        else:
            user = user_model(email=email, is_active=True, is_superuser=False, is_verified=True)
            user.hashed_password = PasswordHelper().hash("!oauth!")  # sentinel
            if hasattr(user, "full_name"):
                setattr(user, "full_name", full_name)
            session.add(user)
            await session.flush()

        jwt = jwt_strategy.write_token(user)
        return RedirectResponse(url=f"{post_login_redirect}?token={jwt}")

    return r
