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

from svc_infra.api.fastapi.auth.mfa.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.policy import AuthPolicy, DefaultAuthPolicy
from svc_infra.api.fastapi.auth.settings import get_auth_settings, parse_redirect_allow_hosts
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.api.fastapi.paths.auth import (
    OAUTH_CALLBACK_PATH,
    OAUTH_LOGIN_PATH,
    OAUTH_REFRESH_PATH,
)
from svc_infra.security.models import RefreshToken
from svc_infra.security.session import issue_session_and_refresh, rotate_session_refresh


def _gen_pkce_pair() -> tuple[str, str]:
    """Generate PKCE verifier and challenge pair for OAuth security."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _validate_redirect(url: str, allow_hosts: list[str], *, require_https: bool) -> None:
    """Validate that a redirect URL is allowed and secure."""
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
    """Extract expiration time from OAuth token."""
    if not isinstance(token, dict):
        return None
    if token.get("expires_at") is not None:
        try:
            v = float(token["expires_at"])
            if v > 1e12:  # ms -> s
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            pass
    if token.get("expires_in") is not None:
        try:
            secs = int(token["expires_in"])
            return datetime.now(timezone.utc) + timedelta(seconds=secs)
        except Exception:
            pass
    return None


def _cookie_name(st) -> str:
    """Get the cookie name with appropriate security prefix."""
    name = getattr(st, "auth_cookie_name", "svc_auth")
    if st.session_cookie_secure and not st.session_cookie_domain and not name.startswith("__Host-"):
        name = "__Host-" + name
    return name


def _cookie_domain(st):
    """Get the cookie domain setting."""
    d = getattr(st, "session_cookie_domain", None)
    return d or None


def _register_oauth_providers(oauth: OAuth, providers: Dict[str, Dict[str, Any]]) -> None:
    """Register all OAuth providers with the OAuth client."""
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


def _handle_oauth_error(
    request: Request, provider: str, error: str, description: str = ""
) -> RedirectResponse:
    """Handle OAuth errors by clearing session state and redirecting."""
    # Clear transient oauth session state so user can retry
    for k in ("state", "pkce_verifier", "nonce", "next"):
        request.session.pop(f"oauth:{provider}:{k}", None)

    st = get_auth_settings()
    fallback = str(getattr(st, "post_login_redirect", "/"))
    qs = urlencode(
        {
            "oauth_error": error,
            "error_description": description,
        }
    )
    return RedirectResponse(url=f"{fallback}?{qs}", status_code=status.HTTP_302_FOUND)


async def _extract_user_info_oidc(
    request: Request,
    client,
    token: dict,
    nonce: str | None,
) -> tuple[str | None, str | None, str | None, bool | None, dict]:
    """Extract user information from OIDC provider."""
    claims: dict[str, Any] = {}
    id_token_present = isinstance(token, dict) and "id_token" in token

    if id_token_present:
        try:
            claims = await client.parse_id_token(token, nonce=nonce)
        except TypeError:
            try:
                claims = await client.parse_id_token(request, token, nonce)
            except Exception:
                claims = {}
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

    if not email:
        try:
            ui = await client.userinfo(token=token)
            email = ui.get("email") or email
            full_name = ui.get("name") or full_name
        except Exception:
            pass

    return email, full_name, provider_user_id, email_verified, claims


async def _extract_user_info_github(
    client, token: dict
) -> tuple[str | None, str | None, str | None, bool | None, dict]:
    """Extract user information from GitHub provider."""
    u = (await client.get("user", token=token)).json()
    emails_resp = (await client.get("user/emails", token=token)).json()
    primary = next((e for e in emails_resp if e.get("primary") and e.get("verified")), None)

    if not primary:
        raise HTTPException(400, "unverified_email")

    email = primary["email"]
    email_verified = True
    full_name = u.get("name") or u.get("login")
    provider_user_id = str(u.get("id")) if isinstance(u, dict) and u.get("id") is not None else None

    return email, full_name, provider_user_id, email_verified, {"user": u}


async def _extract_user_info_linkedin(
    client, token: dict
) -> tuple[str | None, str | None, str | None, bool | None, dict]:
    """Extract user information from LinkedIn provider."""
    me = (await client.get("me", token=token)).json()
    provider_user_id = (
        str(me.get("id")) if isinstance(me, dict) and me.get("id") is not None else None
    )

    em = (
        await client.get("emailAddress?q=members&projection=(elements*(handle~))", token=token)
    ).json()

    email = None
    els = em.get("elements") or []
    if els and "handle~" in els[0]:
        email = els[0]["handle~"].get("emailAddress")

    lf = (((me.get("firstName") or {}).get("localized")) or {}).values()
    ll = (((me.get("lastName") or {}).get("localized")) or {}).values()
    first = next(iter(lf), None)
    last = next(iter(ll), None)
    full_name = " ".join([x for x in [first, last] if x])
    email_verified = True

    return email, full_name, provider_user_id, email_verified, {"me": me}


async def _extract_user_info_from_provider(
    request: Request,
    client,
    token: dict,
    provider: str,
    cfg: dict,
    nonce: str | None = None,
) -> tuple[str | None, str | None, str | None, bool | None, dict | None]:
    """Extract user information from OAuth provider based on provider type."""
    kind = cfg.get("kind")

    if kind == "oidc":
        return await _extract_user_info_oidc(request, client, token, nonce)
    elif kind == "github":
        return await _extract_user_info_github(client, token)
    elif kind == "linkedin":
        return await _extract_user_info_linkedin(client, token)
    else:
        raise HTTPException(400, "Unsupported provider kind")


async def _find_or_create_user(session, user_model, email: str, full_name: str | None) -> Any:
    """Find existing user by email or create a new one."""
    existing = (await session.execute(select(user_model).filter_by(email=email))).scalars().first()

    if existing:
        return existing

    user = user_model(
        email=email,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )

    # Set hashed password for OAuth users
    if hasattr(user, "hashed_password"):
        user.hashed_password = PasswordHelper().hash("!oauth!")
    elif hasattr(user, "password_hash"):
        user.password_hash = PasswordHelper().hash("!oauth!")

    if full_name and hasattr(user, "full_name"):
        setattr(user, "full_name", full_name)

    session.add(user)
    await session.flush()  # ensure user.id exists
    return user


async def _find_user_by_provider_link(
    session, provider_account_model, user_model, provider: str, provider_user_id: str
) -> Any | None:
    """Find user by existing provider account link."""
    if provider_account_model is None or not provider_user_id:
        return None

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
        return await session.get(user_model, existing_link.user_id)

    return None


async def _update_provider_account(
    session,
    provider_account_model,
    user,
    provider: str,
    provider_user_id: str,
    token: dict,
    raw_claims: dict | None,
) -> None:
    """Create or update provider account link."""
    if provider_account_model is None or not provider_user_id:
        return

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

    tok = token if isinstance(token, dict) else {}
    access_token = tok.get("access_token")
    refresh_token = tok.get("refresh_token")
    expires_at = _coerce_expires_at(tok)

    if not link:
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
        # Update existing link if values have changed
        dirty = False
        if hasattr(link, "access_token") and access_token and link.access_token != access_token:
            link.access_token = access_token
            dirty = True
        if hasattr(link, "refresh_token") and refresh_token and link.refresh_token != refresh_token:
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


def _determine_final_redirect_url(request: Request, provider: str, post_login_redirect: str) -> str:
    """Determine the final redirect URL after successful authentication."""
    st = get_auth_settings()
    # Prioritize the parameter passed to the router over settings
    redirect_url = str(post_login_redirect or getattr(st, "post_login_redirect", "/"))
    allow_hosts = parse_redirect_allow_hosts(getattr(st, "redirect_allow_hosts_raw", None))
    require_https = bool(getattr(st, "session_cookie_secure", False))

    _validate_redirect(redirect_url, allow_hosts, require_https=require_https)

    # Prefer ?next or the stashed value from /login
    nxt = request.query_params.get("next") or request.session.pop(f"oauth:{provider}:next", None)
    if nxt:
        try:
            _validate_redirect(nxt, allow_hosts, require_https=require_https)
            redirect_url = nxt
        except HTTPException:
            pass

    return redirect_url


async def _validate_oauth_state(request: Request, provider: str) -> tuple[str | None, str | None]:
    """Validate OAuth state and extract session values."""
    provided_state = request.query_params.get("state")
    expected_state = request.session.pop(f"oauth:{provider}:state", None)
    verifier = request.session.pop(f"oauth:{provider}:pkce_verifier", None)
    nonce = request.session.pop(f"oauth:{provider}:nonce", None)

    if not expected_state or provided_state != expected_state:
        raise HTTPException(400, "invalid_state")

    return verifier, nonce


async def _exchange_code_for_token(client, request: Request, verifier: str | None, provider: str):
    """Exchange OAuth authorization code for access token."""
    try:
        return await client.authorize_access_token(request, code_verifier=verifier)
    except OAuthError as e:
        return _handle_oauth_error(request, provider, e.error, e.description or "")


async def _process_user_authentication(
    session,
    user_model,
    provider_account_model,
    provider: str,
    email: str,
    full_name: str | None,
    provider_user_id: str,
    token: dict,
    raw_claims: dict | None,
) -> Any:
    """Process user authentication by finding or creating user and updating provider account."""
    # Try resolving by existing provider link first
    user = await _find_user_by_provider_link(
        session, provider_account_model, user_model, provider, provider_user_id
    )

    # Fallback: resolve/create by email
    if user is None:
        user = await _find_or_create_user(session, user_model, email, full_name)

    # Ensure provider link exists
    await _update_provider_account(
        session, provider_account_model, user, provider, provider_user_id, token, raw_claims
    )

    return user


async def _validate_and_decode_jwt_token(raw_token: str) -> str:
    """Validate and decode JWT token to extract user ID."""
    st = get_auth_settings()
    secret = (
        st.jwt.secret.get_secret_value()
        if getattr(st, "jwt", None) and getattr(st.jwt, "secret", None)
        else "dev-change-me"
    )

    try:
        payload = jwt.decode(
            raw_token,
            secret,
            algorithms=["HS256"],
            audience=["fastapi-users:auth"],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "invalid_token")
        return user_id
    except Exception:
        raise HTTPException(401, "invalid_token")


async def _set_cookie_on_response(
    resp: Response,
    auth_backend: AuthenticationBackend,
    user: Any,
    *,
    refresh_raw: str,
) -> None:
    """Set authentication (JWT) and refresh cookies on response."""
    st = get_auth_settings()
    strategy = auth_backend.get_strategy()
    jwt_token = await strategy.write_token(user)

    same_site_lit = cast(Literal["lax", "strict", "none"], str(st.session_cookie_samesite).lower())
    if same_site_lit == "none" and not bool(st.session_cookie_secure):
        raise HTTPException(500, "session_cookie_samesite=None requires session_cookie_secure=True")

    # Access/Auth cookie (short-lived JWT)
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

    # Refresh cookie (opaque token, longer lived)
    resp.set_cookie(
        key=getattr(st, "session_cookie_name", "svc_session"),
        value=refresh_raw,
        max_age=60 * 60 * 24 * 7,  # 7 days default
        httponly=True,
        secure=bool(st.session_cookie_secure),
        samesite=same_site_lit,
        domain=_cookie_domain(st),
        path="/",
    )


def _clean_oauth_session_state(request: Request, provider: str) -> None:
    """Clean up transient OAuth session state."""
    for k in ("state", "pkce_verifier", "nonce", "next"):
        request.session.pop(f"oauth:{provider}:{k}", None)


async def _handle_mfa_redirect(
    policy: AuthPolicy, user: Any, redirect_url: str
) -> RedirectResponse | None:
    """Handle MFA redirect if required, return None if MFA not needed."""
    if not await policy.should_require_mfa(user):
        return None

    pre = await get_mfa_pre_jwt_writer().write(user)
    qs = urlencode({"mfa": "required", "pre_token": pre})
    return RedirectResponse(url=f"{redirect_url}?{qs}", status_code=status.HTTP_302_FOUND)


def oauth_router_with_backend(
    user_model: type,
    auth_backend: AuthenticationBackend,
    providers: Dict[str, Dict[str, Any]],
    post_login_redirect: str = "/",
    provider_account_model: type | None = None,
    auth_policy: AuthPolicy | None = None,
) -> APIRouter:
    return _create_oauth_router(
        user_model,
        auth_backend,
        providers,
        post_login_redirect,
        provider_account_model,
        auth_policy,
    )


def _create_oauth_router(
    user_model: type,
    auth_backend: AuthenticationBackend,
    providers: Dict[str, Dict[str, Any]],
    post_login_redirect: str = "/",
    provider_account_model: type | None = None,
    auth_policy: AuthPolicy | None = None,
) -> APIRouter:
    """Create OAuth router with all endpoints."""
    oauth = OAuth()
    policy: AuthPolicy = auth_policy or DefaultAuthPolicy(get_auth_settings())

    # Register all providers
    _register_oauth_providers(oauth, providers)

    router = public_router()

    @router.get(
        OAUTH_LOGIN_PATH,
        description="Login with OAuth provider",
    )
    async def oauth_login(request: Request, provider: str):
        """Initiate OAuth login flow."""
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        verifier, challenge = _gen_pkce_pair()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)

        request.session[f"oauth:{provider}:pkce_verifier"] = verifier
        request.session[f"oauth:{provider}:state"] = state
        request.session[f"oauth:{provider}:nonce"] = nonce

        # Stash 'next' across the round-trip (some IdPs drop unknown params)
        nxt = request.query_params.get("next")
        if nxt:
            request.session[f"oauth:{provider}:next"] = nxt

        redirect_uri = str(request.url_for("oauth_callback", provider=provider))
        return await client.authorize_redirect(
            request,
            redirect_uri,
            code_challenge=challenge,
            code_challenge_method="S256",
            state=state,
            nonce=nonce,
        )

    @router.get(
        OAUTH_CALLBACK_PATH,
        name="oauth_callback",
        responses={302: {"description": "Redirect to app (or MFA redirect)."}},
        description="OAuth callback endpoint.",
    )
    async def oauth_callback(request: Request, provider: str, session: SqlSessionDep):
        """Handle OAuth callback and complete authentication."""
        # Handle provider-side errors up front
        if err := request.query_params.get("error"):
            description = request.query_params.get("error_description", "")
            return _handle_oauth_error(request, provider, err, description)

        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(404, "Provider not configured")

        # Validate state and get session values
        verifier, nonce = await _validate_oauth_state(request, provider)

        # Exchange code for token
        token = await _exchange_code_for_token(client, request, verifier, provider)
        if isinstance(token, RedirectResponse):  # Error occurred
            return token

        # Extract user information from provider
        cfg = providers.get(provider, {})
        email, full_name, provider_user_id, email_verified, raw_claims = (
            await _extract_user_info_from_provider(request, client, token, provider, cfg, nonce)
        )

        if email_verified is False:
            raise HTTPException(400, "unverified_email")
        if not email:
            raise HTTPException(400, "No email from provider")

        # Process user authentication
        user = await _process_user_authentication(
            session,
            user_model,
            provider_account_model,
            provider,
            email,
            full_name,
            provider_user_id,
            token,
            raw_claims,
        )

        # Reject disabled accounts early
        if not getattr(user, "is_active", True):
            raise HTTPException(401, "account_disabled")

        # Determine final redirect URL
        redirect_url = _determine_final_redirect_url(request, provider, post_login_redirect)

        # Handle MFA if required (do NOT set last_login yet; do it after MFA)
        mfa_response = await _handle_mfa_redirect(policy, user, redirect_url)
        if mfa_response:
            _clean_oauth_session_state(request, provider)
            return mfa_response

        # NEW: set last_login only when we are actually logging in now
        user.last_login = datetime.now(timezone.utc)
        await session.commit()

        # Create session + initial refresh token
        raw_refresh, _rt = await issue_session_and_refresh(
            session,
            user_id=user.id,
            tenant_id=getattr(user, "tenant_id", None),
            user_agent=str(request.headers.get("user-agent", ""))[:512],
            ip_hash=None,
        )

        # Generate JWT token for the response
        strategy = auth_backend.get_strategy()
        jwt_token = await strategy.write_token(user)

        # If redirecting to a different origin, append token as URL fragment for frontend to extract
        # This handles cross-port scenarios like localhost:8000 -> localhost:3000
        parsed_redirect = urlparse(redirect_url)
        request_origin = f"{request.url.scheme}://{request.url.netloc}"
        redirect_origin = f"{parsed_redirect.scheme}://{parsed_redirect.netloc}"

        if redirect_origin and redirect_origin != request_origin:
            # Cross-origin redirect: append token as URL fragment
            # Fragment is not sent to server, only accessible to client-side JS
            separator = "#" if not parsed_redirect.fragment else "&"
            redirect_url = f"{redirect_url}{separator}access_token={jwt_token}"

        # Create response with auth + refresh cookies (for same-origin requests)
        resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
        await _set_cookie_on_response(resp, auth_backend, user, refresh_raw=raw_refresh)

        # Clean up session state
        _clean_oauth_session_state(request, provider)

        # Optional: hook
        if hasattr(policy, "on_login_success"):
            try:
                await policy.on_login_success(user)
            except Exception:
                pass

        return resp

    @router.post(
        OAUTH_REFRESH_PATH,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={204: {"description": "Cookie refreshed"}},
        description="Refresh authentication token.",
    )
    async def refresh(request: Request, session: SqlSessionDep):
        """Refresh authentication token."""
        st = get_auth_settings()

        # Read and validate auth JWT cookie
        name_auth = _cookie_name(st)
        raw_auth = request.cookies.get(name_auth)
        if not raw_auth:
            raise HTTPException(401, "missing_token")

        # Validate and decode JWT token to get user id
        user_id = await _validate_and_decode_jwt_token(raw_auth)

        # Load user
        user = await session.get(user_model, user_id)
        if not user:
            raise HTTPException(401, "invalid_token")

        # Obtain refresh cookie
        refresh_cookie_name = getattr(st, "session_cookie_name", "svc_session")
        raw_refresh = request.cookies.get(refresh_cookie_name)
        if not raw_refresh:
            raise HTTPException(401, "missing_refresh_token")

        # Lookup refresh token row by hash
        from sqlalchemy import select

        from svc_infra.security.models import hash_refresh_token

        token_hash = hash_refresh_token(raw_refresh)
        found: RefreshToken | None = (
            (
                await session.execute(
                    select(RefreshToken).where(RefreshToken.token_hash == token_hash)
                )
            )
            .scalars()
            .first()
        )
        if (
            not found
            or found.revoked_at
            or (found.expires_at and found.expires_at < datetime.now(timezone.utc))
        ):
            raise HTTPException(401, "invalid_refresh_token")

        # Rotate refresh token
        new_raw, _new_rt = await rotate_session_refresh(session, current=found)

        # Write response (204) with new cookies
        resp = Response(status_code=status.HTTP_204_NO_CONTENT)
        await _set_cookie_on_response(resp, auth_backend, user, refresh_raw=new_raw)
        # Policy hook: trigger after successful rotation; suppress hook errors
        if hasattr(policy, "on_token_refresh"):
            try:
                await policy.on_token_refresh(user)
            except Exception:
                pass

        return resp

    # Return router at end of factory
    return router
