"""
Tests for authentication routers and endpoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.routers.account import account_router
from svc_infra.api.fastapi.auth.routers.apikey_router import apikey_router
from svc_infra.api.fastapi.auth.security import Principal, _current_principal
from svc_infra.api.fastapi.db.sql.session import get_session


class FakeApiKey:
    """Lightweight stand-in for the SQLAlchemy ApiKey model."""

    class _Column:
        def __eq__(self, other):
            return ("user_id_eq", other)

    user_id = _Column()

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", uuid4())
        self.user_id = kwargs.pop("user_id", uuid4())
        self.key_prefix = kwargs.pop("key_prefix", "prefix123")
        self.key_hash = kwargs.pop("key_hash", "hashed-secret")
        self.scopes = kwargs.pop("scopes", [])
        self.active = kwargs.pop("active", True)
        self.expires_at = kwargs.pop("expires_at", None)
        self.last_used_at = kwargs.pop("last_used_at", None)
        self.name = kwargs.pop("name", "Test Key")
        for key, value in kwargs.items():
            setattr(self, key, value)

    @staticmethod
    def make_secret() -> tuple[str, str, str]:
        return ("ak_test_plaintext", "prefix123", "hashed-secret")

    @staticmethod
    def hash(plaintext: str) -> str:  # pragma: no cover - helper for compatibility
        return "hashed-secret"

    def mark_used(self):
        self.last_used_at = "used"  # pragma: no cover


async def _call(app: FastAPI, method: str, path: str, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _setup_account_app(session, principal) -> FastAPI:
    app = FastAPI()
    app.include_router(account_router(user_model=Mock()), prefix="/account")
    app.dependency_overrides[_current_principal] = lambda: principal

    async def _session_override():
        return session

    app.dependency_overrides[get_session] = _session_override
    return app


def _setup_apikey_app(session, principal, mocker) -> FastAPI:
    app = FastAPI()
    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.apikey_router.get_apikey_model", return_value=FakeApiKey
    )

    class _SelectStub:
        def __init__(self, model):
            self.model = model
            self._clauses = []

        def where(self, *clauses):
            self._clauses.extend(clauses)
            return self

    mocker.patch(
        "svc_infra.api.fastapi.auth.routers.apikey_router.select",
        side_effect=lambda model: _SelectStub(model),
    )
    app.include_router(apikey_router(), prefix="/auth")
    app.dependency_overrides[_current_principal] = lambda: principal

    async def _session_override():
        return session

    app.dependency_overrides[get_session] = _session_override
    return app


@pytest.mark.asyncio
async def test_disable_account_marks_user_inactive():
    session = Mock()
    session.commit = AsyncMock()
    user = SimpleNamespace(is_active=True, disabled_reason=None)

    app = _setup_account_app(session, Principal(user=user))

    response = await _call(app, "PATCH", "/account/disable", json={"reason": "manual"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "disabled"}
    assert user.is_active is False
    assert user.disabled_reason == "manual"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_account_soft_sets_disabled_reason():
    session = Mock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    user = SimpleNamespace(is_active=True, disabled_reason=None)

    app = _setup_account_app(session, Principal(user=user))

    response = await _call(app, "DELETE", "/account/delete")

    assert response.status_code == 204
    assert user.is_active is False
    assert user.disabled_reason == "user_soft_deleted"
    session.commit.assert_awaited_once()
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_account_hard_invokes_delete():
    session = Mock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    user = SimpleNamespace(is_active=True, disabled_reason=None)

    app = _setup_account_app(session, Principal(user=user))

    response = await _call(app, "DELETE", "/account/delete?hard=true")

    assert response.status_code == 204
    session.delete.assert_awaited_once_with(user)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_api_key_returns_plaintext_and_persists(mocker):
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    principal_user = SimpleNamespace(id=uuid4(), is_superuser=False)

    app = _setup_apikey_app(session, Principal(user=principal_user), mocker)

    response = await _call(
        app,
        "POST",
        "/auth/keys",
        json={"name": "CI Key", "scopes": ["read"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "CI Key"
    assert body["key"] == "ak_test_plaintext"
    assert body["key_prefix"] == "prefix123"
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_api_keys_returns_sanitized_rows(mocker):
    owner_id = uuid4()
    keys = [
        FakeApiKey(id=uuid4(), user_id=owner_id, name="Key A", scopes=["read"], active=True),
        FakeApiKey(id=uuid4(), user_id=owner_id, name="Key B", scopes=[], active=False),
    ]

    session = Mock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: keys))
    )
    principal_user = SimpleNamespace(id=owner_id, is_superuser=False)

    app = _setup_apikey_app(session, Principal(user=principal_user), mocker)

    response = await _call(app, "GET", "/auth/keys")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Key A"
    assert data[0]["key"] is None  # plaintext should never be returned


@pytest.mark.asyncio
async def test_revoke_api_key_marks_key_inactive(mocker):
    session = Mock()
    session.commit = AsyncMock()
    api_key = FakeApiKey(user_id=uuid4(), active=True)
    session.get = AsyncMock(return_value=api_key)

    principal_user = SimpleNamespace(id=api_key.user_id, is_superuser=False)
    app = _setup_apikey_app(session, Principal(user=principal_user), mocker)

    response = await _call(app, "POST", f"/auth/keys/{api_key.id}/revoke")

    assert response.status_code == 204
    assert api_key.active is False
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_api_key_requires_force_for_active_keys(mocker):
    session = Mock()
    api_key = FakeApiKey(user_id=uuid4(), active=True)
    session.get = AsyncMock(return_value=api_key)
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    app = _setup_apikey_app(session, Principal(user=SimpleNamespace(id=api_key.user_id)), mocker)

    response = await _call(app, "DELETE", f"/auth/keys/{api_key.id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "key_active; revoke first or pass force=true"
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_api_key_force_deletes(mocker):
    session = Mock()
    api_key = FakeApiKey(user_id=uuid4(), active=True)
    session.get = AsyncMock(return_value=api_key)
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    app = _setup_apikey_app(
        session,
        Principal(user=SimpleNamespace(id=api_key.user_id, is_superuser=False)),
        mocker,
    )

    response = await _call(app, "DELETE", f"/auth/keys/{api_key.id}?force=true")

    assert response.status_code == 204
    session.delete.assert_awaited_once_with(api_key)
    session.commit.assert_awaited_once()
