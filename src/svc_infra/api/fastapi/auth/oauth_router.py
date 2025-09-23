from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, Literal, cast
from urllib.parse import urlencode, urlparse

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from starlette import status
from starlette.responses import Response

from svc_infra.api.fastapi import DualAPIRouter
from svc_infra.api.fastapi.auth.settings import get_auth_settings, parse_redirect_allow_hosts
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


def _gen_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _validate_redirect(url: str, allow_hosts: list[str], *, require_https: bool) -> None:
    p = urlparse(url)
    host_port = p.hostname.lower() + (f":{p.port}" if p.port else "")
    allowed = {h.lower() for h in allow_hosts}
    if host_port not in allowed and p.hostname.lower() not in allowed:
        raise HTTPException(400, "redirect_not_allowed")
    if require_https and p.scheme != "https":
        raise HTTPException(400, "https_required")


def oauth_router_with_backend(
    user_model: type,
    auth_backend: AuthenticationBackend,
    providers: Dict[str, Dict[str, Any]],
    post_login_redirect: str = "/",
    prefix: str = "/auth/oauth",
) -> DualAPIRouter:
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
            pass

    router = DualAPIRouter(prefix=prefix, tags=["auth:oauth"])

    @router.get("/{provider}/login")
    async def oauth_login(request: Request, provider: str):
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        verifier, challenge = _gen_pkce_pair()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)

        request.session[f"oauth:{provider}:pkce_verifier"] = verifier
        request.session[f"oauth:{provider}:state"] = state
        request.session[f"oauth:{provider}:nonce"] = nonce

        redirect_uri = str(request.url_for("oauth_callback", provider=provider))
        return await client.authorize_redirect(
            request,
            redirect_uri,
            code_challenge=challenge,
            code_challenge_method="S256",
            state=state,
            nonce=nonce,
        )

    @router.get("/{provider}/callback", name="oauth_callback")
    async def oauth_callback(request: Request, provider: str, session: SqlSessionDep):
        # Handle provider-side errors up front
        if err := request.query_params.get("error"):
            # clear transient oauth session state so user can retry
            request.session.pop(f"oauth:{provider}:state", None)
            request.session.pop(f"oauth:{provider}:pkce_verifier", None)
            request.session.pop(f"oauth:{provider}:nonce", None)

            st = get_auth_settings()
            fallback = str(getattr(st, "post_login_redirect", "/"))
            # send the error back to frontend (adjust route as you like)
            qs = urlencode(
                {
                    "oauth_error": err,
                    "error_description": request.query_params.get("error_description", ""),
                }
            )
            return RedirectResponse(url=f"{fallback}?{qs}", status_code=status.HTTP_302_FOUND)

        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        provided_state = request.query_params.get("state")
        expected_state = request.session.pop(f"oauth:{provider}:state", None)
        verifier = request.session.pop(f"oauth:{provider}:pkce_verifier", None)
        nonce = request.session.pop(f"oauth:{provider}:nonce", None)
        if not expected_state or provided_state != expected_state:
            raise HTTPException(400, "invalid_state")

        try:
            token = await client.authorize_access_token(request, code_verifier=verifier)
        except OAuthError as e:
            # clear transient state so user can retry
            for k in ("state", "pkce_verifier", "nonce"):
                request.session.pop(f"oauth:{provider}:{k}", None)
            st = get_auth_settings()
            fallback = str(getattr(st, "post_login_redirect", "/"))
            qs = urlencode({"oauth_error": e.error, "error_description": e.description or ""})
            return RedirectResponse(f"{fallback}?{qs}", status_code=status.HTTP_302_FOUND)

        cfg = providers.get(provider, {})
        kind = cfg.get("kind")

        email: str | None = None
        full_name: str | None = None

        if kind == "oidc":
            claims: dict[str, Any] = {}
            id_token_present = isinstance(token, dict) and "id_token" in token

            if id_token_present:
                # Try both Authlib signatures and make sure nonce is provided
                try:
                    # Newer-style: parse_id_token(token, nonce=...)
                    claims = await client.parse_id_token(token, nonce=nonce)
                except TypeError:
                    # Older-style: parse_id_token(request, token, nonce)
                    claims = await client.parse_id_token(request, token, nonce)
                except Exception:
                    # If anything else goes wrong, we’ll fall back to userinfo
                    claims = {}

            # If we still don't have claims, or there was no id_token, use UserInfo
            if not claims:
                try:
                    claims = await client.userinfo(token=token)
                except Exception:
                    raise HTTPException(400, "oidc_userinfo_failed")

            # If provider sent a nonce in claims, verify it (only when present)
            if nonce and claims.get("nonce") and claims["nonce"] != nonce:
                raise HTTPException(400, "invalid_nonce")

            email = claims.get("email")
            full_name = claims.get("name") or claims.get("preferred_username")

            # Last-ditch: try userinfo again to grab email if missing
            if not email:
                try:
                    ui = await client.userinfo(token=token)
                    email = ui.get("email") or email
                    full_name = ui.get("name") or full_name
                except Exception:
                    pass

        elif kind == "github":
            u = (await client.get("user", token=token)).json()
            emails_resp = (await client.get("user/emails", token=token)).json()
            primary = next((e for e in emails_resp if e.get("primary") and e.get("verified")), None)
            email = (primary or (emails_resp[0] if emails_resp else {})).get("email")
            full_name = u.get("name") or u.get("login")

        elif kind == "linkedin":
            me = (await client.get("me", token=token)).json()
            em = (
                await client.get(
                    "emailAddress?q=members&projection=(elements*(handle~))", token=token
                )
            ).json()
            els = em.get("elements") or []
            if els and "handle~" in els[0]:
                email = els[0]["handle~"].get("emailAddress")
            lf = (((me.get("firstName") or {}).get("localized")) or {}).values()
            ll = (((me.get("lastName") or {}).get("localized")) or {}).values()
            first = next(iter(lf), None)
            last = next(iter(ll), None)
            full_name = " ".join([x for x in [first, last] if x])

        else:
            raise HTTPException(400, "Unsupported provider kind")

        if not email:
            raise HTTPException(400, "No email from provider")

        # Upsert user (by email)
        existing = (
            (await session.execute(select(user_model).filter_by(email=email))).scalars().first()
        )
        if existing:
            user = existing
        else:
            user = user_model(email=email, is_active=True, is_superuser=False, is_verified=True)
            if hasattr(user, "hashed_password"):
                user.hashed_password = PasswordHelper().hash("!oauth!")
            elif hasattr(user, "password_hash"):
                user.password_hash = PasswordHelper().hash("!oauth!")
            if full_name and hasattr(user, "full_name"):
                setattr(user, "full_name", full_name)
            session.add(user)
            await session.flush()

        # Issue JWT
        strategy = auth_backend.get_strategy()
        jwt_token = await strategy.write_token(user)

        # Set HttpOnly cookie and redirect (allow-listed)
        st = get_auth_settings()
        redirect_url = str(
            getattr(st, "post_login_redirect", post_login_redirect) or post_login_redirect
        )

        allow_hosts = parse_redirect_allow_hosts(getattr(st, "redirect_allow_hosts_raw", None))
        require_https = bool(getattr(st, "session_cookie_secure", False))

        _validate_redirect(redirect_url, allow_hosts, require_https=require_https)

        nxt = request.query_params.get("next")
        if nxt:
            try:
                _validate_redirect(nxt, allow_hosts, require_https=require_https)
                redirect_url = nxt
            except HTTPException:
                pass

        same_site_lit = cast(
            Literal["lax", "strict", "none"], str(st.session_cookie_samesite).lower()
        )
        if same_site_lit == "none" and not bool(st.session_cookie_secure):
            # auto-fix to lax or raise; I suggest raising in dev
            raise HTTPException(
                500, "session_cookie_samesite=None requires session_cookie_secure=True"
            )
        resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        name = st.session_cookie_name
        if (
            st.session_cookie_secure
            and not st.session_cookie_domain
            and st.session_cookie_name[:7] != "__Host-"
        ):
            name = "__Host-" + st.session_cookie_name

        resp.set_cookie(
            key=name,
            value=jwt_token,
            max_age=st.session_cookie_max_age_seconds,
            httponly=True,
            secure=bool(st.session_cookie_secure),
            samesite=same_site_lit,  # "none" only if secure
            domain=st.session_cookie_domain,  # must be None for __Host-
            path="/",
        )
        return resp

    @router.post("/logout")
    async def logout():
        st = get_auth_settings()
        name = st.session_cookie_name
        if (
            st.session_cookie_secure
            and not st.session_cookie_domain
            and not name.startswith("__Host-")
        ):
            name = "__Host-" + name
        resp = Response(status_code=204)
        resp.delete_cookie(
            key=name,
            domain=st.session_cookie_domain,  # must be None for __Host-
            path="/",
        )
        return resp

    return router
