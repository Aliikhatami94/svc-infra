"""Tests for OAuth refresh endpoint hooks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.routers.oauth_router import oauth_router_with_backend
from svc_infra.api.fastapi.db.sql.session import get_session


async def _call(app: FastAPI, method: str, path: str, **kwargs):
    cookies = kwargs.pop("cookies", None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        if cookies:
            client.cookies.update(cookies)
        return await client.request(method, path, **kwargs)


def _build_refresh_app(policy: SimpleNamespace, mocker):
    class DummyUserModel:
        pass

    auth_backend = Mock()
    router = oauth_router_with_backend(
        user_model=DummyUserModel,
        auth_backend=auth_backend,
        providers={},
        auth_policy=policy,
    )

    app = FastAPI()
    app.include_router(router, prefix="/oauth")

    user = SimpleNamespace(id="user-123")
    found = SimpleNamespace(revoked_at=None, expires_at=None, session=SimpleNamespace())

    session = Mock()
    session.get = AsyncMock(return_value=user)
    session.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(first=lambda: found)
        )
    )

    async def _session_override():
        return session

    app.dependency_overrides[get_session] = _session_override

    settings = SimpleNamespace(
        auth_cookie_name="svc_auth",
        session_cookie_secure=False,
        session_cookie_domain=None,
        session_cookie_samesite="lax",
        session_cookie_max_age_seconds=3600,
        session_cookie_name="svc_session",
        jwt=SimpleNamespace(secret=SimpleNamespace(get_secret_value=lambda: "secret")),
    )

    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.oauth_router.get_auth_settings",
        return_value=settings,
    )
    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.oauth_router._validate_and_decode_jwt_token",
        new=AsyncMock(return_value="user-123"),
    )
    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.oauth_router.rotate_session_refresh",
        new=AsyncMock(return_value=("new-refresh", object())),
    )
    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.oauth_router._set_cookie_on_response",
        new=AsyncMock(return_value=None),
    )

    return app, session, user


@pytest.mark.asyncio
async def test_refresh_triggers_policy_hook(mocker):
    policy = SimpleNamespace(on_token_refresh=AsyncMock())
    app, session, user = _build_refresh_app(policy, mocker)

    response = await _call(
        app,
        "POST",
        "/oauth/refresh",
        cookies={"svc_auth": "jwt-token", "svc_session": "raw-refresh"},
    )

    assert response.status_code == 204
    policy.on_token_refresh.assert_awaited_once_with(user)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_policy_hook_errors_are_suppressed(mocker):
    policy = SimpleNamespace(
        on_token_refresh=AsyncMock(side_effect=RuntimeError("boom"))
    )
    app, _session, user = _build_refresh_app(policy, mocker)

    response = await _call(
        app,
        "POST",
        "/oauth/refresh",
        cookies={"svc_auth": "jwt-token", "svc_session": "raw-refresh"},
    )

    assert response.status_code == 204
    assert policy.on_token_refresh.await_count == 1
    assert policy.on_token_refresh.await_args[0][0] is user

