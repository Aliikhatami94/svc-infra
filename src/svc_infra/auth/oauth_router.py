from __future__ import annotations

from typing import Any, Dict

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


def oauth_router_with_backend(
    user_model: type,
    auth_backend: AuthenticationBackend,
    providers: Dict[str, Dict[str, Any]],
    post_login_redirect: str = "/",
    prefix: str = "/auth/oauth",
) -> APIRouter:
    oauth = OAuth()

    # Register all providers
    for name, cfg in providers.items():
        kind = cfg.get("kind")
        if kind == "oidc":
            oauth.register(
                name,
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                server_metadata_url=f"{cfg['issuer'].rstrip('/')}/.well-known/openid-configuration",
                client_kwargs={"scope": cfg.get("scope", "openid email profile")},
            )
        elif kind in ("github", "linkedin"):
            oauth.register(
                name,
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                authorize_url=cfg["authorize_url"],
                access_token_url=cfg["access_token_url"],
                api_base_url=cfg["api_base_url"],
                client_kwargs={"scope": cfg.get("scope", "")},
            )
        else:
            # you can add more branches (facebook, apple*) as needed
            pass

    r = APIRouter(prefix=prefix, tags=["auth:oauth"])

    @r.get("/{provider}/login")
    async def oauth_login(request: Request, provider: str):
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")
        redirect_uri = request.url_for("oauth_callback", provider=provider)
        return await client.authorize_redirect(request, str(redirect_uri))

    @r.get("/{provider}/callback", name="oauth_callback")
    async def oauth_callback(request: Request, provider: str, session: SqlSessionDep):
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        token = await client.authorize_access_token(request)

        email = None

        cfg = providers.get(provider, {})
        kind = cfg.get("kind")

        if kind == "oidc":
            userinfo = token.get("userinfo") or await client.parse_id_token(request, token)
            email = userinfo.get("email")
            full_name = userinfo.get("name") or userinfo.get("preferred_username")
        elif kind == "github":
            resp = await client.get("user", token=token)
            data = resp.json()
            email = data.get("email")
            if not email:
                emails = (await client.get("user/emails", token=token)).json()
                primary = next((e for e in emails if e.get("primary")), emails[0] if emails else {})
                email = primary.get("email")
            full_name = data.get("name") or data.get("login")
        elif kind == "linkedin":
            # profile
            me = (await client.get("me", token=token)).json()
            # email
            em = (
                await client.get(
                    "emailAddress?q=members&projection=(elements*(handle~))",
                    token=token,
                )
            ).json()
            elements = em.get("elements") or []
            if elements and "handle~" in elements[0]:
                email = elements[0]["handle~"].get("emailAddress")
            localizedFirst = (((me.get("firstName") or {}).get("localized")) or {}).values()
            localizedLast = (((me.get("lastName") or {}).get("localized")) or {}).values()
            first = next(iter(localizedFirst), None)
            last = next(iter(localizedLast), None)
            full_name = " ".join([x for x in [first, last] if x])
        else:
            raise HTTPException(400, "Unsupported provider kind")

        if not email:
            raise HTTPException(400, "No email from provider")

        # Upsert user
        existing = (
            (await session.execute(select(user_model).filter_by(email=email))).scalars().first()
        )
        if existing:
            user = existing
        else:
            user = user_model(email=email, is_active=True, is_superuser=False, is_verified=True)
            user.hashed_password = PasswordHelper().hash("!oauth!")
            if hasattr(user, "full_name"):
                setattr(user, "full_name", full_name)
            session.add(user)
            await session.flush()

        jwt = (auth_backend.get_strategy)().write_token(user)
        return RedirectResponse(url=f"{post_login_redirect}?token={jwt}")

    return r
