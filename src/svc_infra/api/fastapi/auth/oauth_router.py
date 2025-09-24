from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, cast
from urllib.parse import urlencode, urlparse

import jwt
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from starlette import status
from starlette.responses import Response

from svc_infra.api.fastapi.auth.settings import get_auth_settings, parse_redirect_allow_hosts
from svc_infra.api.fastapi.auth.sugar import public_router
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


def _gen_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _validate_redirect(url: str, allow_hosts: list[str], *, require_https: bool) -> None:
    p = urlparse(url)
    if not p.netloc:
        return
    host_port = p.hostname.lower() + (f":{p.port}" if p.port else "")
    allowed = {h.lower() for h in allow_hosts}
    if host_port not in allowed and p.hostname.lower() not in allowed:
        raise HTTPException(400, "redirect_not_allowed")
    if require_https and p.scheme != "https":
        raise HTTPException(400, "https_required")


def _coerce_expires_at(token: dict | None) -> datetime | None:
    if not isinstance(token, dict):
        return None
    # Prefer absolute expires_at if present
    if token.get("expires_at") is not None:
        try:
            v = float(token["expires_at"])
            # Some providers return ms; normalize
            if v > 1e12:  # heuristic: ms epoch
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            pass
    # Fallback to expires_in (relative)
    if token.get("expires_in") is not None:
        try:
            secs = int(token["expires_in"])
            return datetime.now(timezone.utc) + timedelta(seconds=secs)
        except Exception:
            pass
    return None


def _cookie_name(st) -> str:
    # use the dedicated auth cookie name, NOT the Starlette session one
    name = getattr(st, "auth_cookie_name", "svc_auth")
    if st.session_cookie_secure and not st.session_cookie_domain and not name.startswith("__Host-"):
        name = "__Host-" + name
    return name


def _cookie_domain(st):
    # IMPORTANT: return None for localhost/dev instead of "" or invalid host
    d = getattr(st, "session_cookie_domain", None)
    return d or None


def oauth_router_with_backend(
    user_model: type,
    auth_backend: AuthenticationBackend,
    providers: Dict[str, Dict[str, Any]],
    post_login_redirect: str = "/",
    prefix: str = "/auth/oauth",
    provider_account_model: type | None = None,
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
            pass

    router = public_router(prefix=prefix, tags=["auth:oauth"])

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
        provider_user_id: str | None = None
        email_verified: bool | None = None

        if kind == "oidc":
            claims: dict[str, Any] = {}
            id_token_present = isinstance(token, dict) and "id_token" in token

            if id_token_present:
                try:
                    claims = await client.parse_id_token(token, nonce=nonce)  # newer Authlib
                except TypeError:
                    claims = await client.parse_id_token(request, token, nonce)  # older signature
                except Exception:
                    claims = {}

            if not claims:
                try:
                    claims = await client.userinfo(token=token)
                except Exception:
                    raise HTTPException(400, "oidc_userinfo_failed")

            if nonce and claims.get("nonce") and claims["nonce"] != nonce:
                raise HTTPException(400, "invalid_nonce")

            email = claims.get("email")
            full_name = claims.get("name") or claims.get("preferred_username")
            email_verified = bool(claims.get("email_verified", True))

            provider_user_id = None
            sub_or_oid = claims.get("sub") or claims.get("oid")
            if sub_or_oid is not None:
                provider_user_id = str(sub_or_oid).strip()

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
            if not primary:
                raise HTTPException(400, "unverified_email")
            email = primary["email"]
            email_verified = True
            full_name = u.get("name") or u.get("login")
            provider_user_id = (
                str(u.get("id")) if isinstance(u, dict) and u.get("id") is not None else None
            )

        elif kind == "linkedin":
            me = (await client.get("me", token=token)).json()
            provider_user_id = (
                str(me.get("id")) if isinstance(me, dict) and me.get("id") is not None else None
            )
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
            email_verified = True

        else:
            raise HTTPException(400, "Unsupported provider kind")

        if email_verified is False:
            # Stop here—don’t create/link accounts on unverified addresses.
            raise HTTPException(400, "unverified_email")

        if not email:
            raise HTTPException(400, "No email from provider")

        # --- Try resolving by an existing provider link first ----------------
        user = None
        existing_link = None
        if provider_account_model is not None and provider_user_id:
            existing_link = (
                (
                    await session.execute(
                        select(provider_account_model).filter_by(
                            provider=provider,
                            provider_account_id=provider_user_id,
                        )
                    )
                )
                .scalars()
                .first()
            )
            if existing_link:
                user = await session.get(user_model, existing_link.user_id)

        # --- Fallback: resolve/create by email (previous logic) --------------
        if user is None:
            existing = (
                (await session.execute(select(user_model).filter_by(email=email))).scalars().first()
            )
            if existing:
                user = existing
            else:
                user = user_model(
                    email=email,
                    is_active=True,
                    is_superuser=False,
                    is_verified=True,
                )
                # Keep compatibility with FastAPI Users field names
                if hasattr(user, "hashed_password"):
                    user.hashed_password = PasswordHelper().hash("!oauth!")
                elif hasattr(user, "password_hash"):
                    user.password_hash = PasswordHelper().hash("!oauth!")
                if full_name and hasattr(user, "full_name"):
                    setattr(user, "full_name", full_name)

                session.add(user)
                await session.flush()  # ensure user.id exists

        # --- Ensure provider link exists ------------------------------------
        if provider_account_model is not None and provider_user_id:
            link = (
                (
                    await session.execute(
                        select(provider_account_model).filter_by(
                            provider=provider,
                            provider_account_id=provider_user_id,
                        )
                    )
                )
                .scalars()
                .first()
            )

            # Optional token/claims payloads (only set if your ProviderAccount has these columns)
            tok = token if isinstance(token, dict) else {}
            access_token = tok.get("access_token")
            refresh_token = tok.get("refresh_token")
            expires_at = _coerce_expires_at(tok)  # <-- convert to datetime
            raw_claims = None
            if kind == "oidc":
                raw_claims = claims
            elif kind == "github":
                raw_claims = {"user": u}
            elif kind == "linkedin":
                raw_claims = {"me": me}

            if not link:
                # Create link
                values = dict(
                    user_id=user.id,
                    provider=provider,
                    provider_account_id=provider_user_id,
                )
                if hasattr(provider_account_model, "access_token"):
                    values["access_token"] = access_token
                if hasattr(provider_account_model, "refresh_token"):
                    values["refresh_token"] = refresh_token
                if hasattr(provider_account_model, "expires_at"):
                    values["expires_at"] = expires_at
                if hasattr(provider_account_model, "raw_claims"):
                    values["raw_claims"] = raw_claims

                session.add(provider_account_model(**values))
                await session.flush()
            else:
                # Refresh token/claims if columns exist
                dirty = False
                if (
                    hasattr(link, "access_token")
                    and access_token
                    and link.access_token != access_token
                ):
                    link.access_token = access_token
                    dirty = True
                if (
                    hasattr(link, "refresh_token")
                    and refresh_token
                    and link.refresh_token != refresh_token
                ):
                    link.refresh_token = refresh_token
                    dirty = True
                if hasattr(link, "expires_at") and expires_at and link.expires_at != expires_at:
                    link.expires_at = expires_at
                    dirty = True
                if hasattr(link, "raw_claims") and raw_claims and link.raw_claims != raw_claims:
                    link.raw_claims = raw_claims
                    dirty = True
                if dirty:
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

        resp.set_cookie(
            key=_cookie_name(st),
            value=jwt_token,
            max_age=st.session_cookie_max_age_seconds,
            httponly=True,
            secure=bool(st.session_cookie_secure),
            samesite=same_site_lit,
            domain=_cookie_domain(st),
            path="/",
        )
        return resp

    @router.post("/refresh")
    async def refresh(request: Request, session: SqlSessionDep):
        st = get_auth_settings()

        # 1) read cookie
        name = _cookie_name(st)
        raw = request.cookies.get(name)
        if not raw:
            raise HTTPException(401, "missing_token")

        # 2) decode token (verify secret + aud)
        try:
            secret = (
                st.jwt.secret.get_secret_value()
                if getattr(st, "jwt", None) and getattr(st.jwt, "secret", None)
                else "dev-change-me"  # same fallback you used for sessions
            )
            # FastAPI Users uses this default audience for JWTs
            payload = jwt.decode(
                raw,
                secret,
                algorithms=["HS256"],
                audience=["fastapi-users:auth"],
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(401, "invalid_token")
        except Exception:
            raise HTTPException(401, "invalid_token")

        # 3) load user
        user = await session.get(user_model, user_id)
        if not user:
            raise HTTPException(401, "invalid_token")

        # 4) mint new token via the same strategy you use at login
        strategy = auth_backend.get_strategy()
        new_token = await strategy.write_token(user)

        # 5) set cookie and return 204
        resp = Response(status_code=204)
        resp.set_cookie(
            key=name,
            value=new_token,
            max_age=st.session_cookie_max_age_seconds,
            httponly=True,
            secure=bool(st.session_cookie_secure),
            samesite=str(st.session_cookie_samesite).lower(),
            domain=_cookie_domain(st),
            path="/",
        )
        return resp

    @router.post("/logout")
    async def logout(request: Request):
        st = get_auth_settings()

        # nuke transient OAuth state
        for k in list(request.session.keys()):
            if k.startswith("oauth:"):
                request.session.pop(k, None)

        # delete auth cookie
        resp = Response(status_code=204)
        resp.delete_cookie(
            key=_cookie_name(st),
            domain=_cookie_domain(st),
            path="/",
        )
        return resp

    return router
