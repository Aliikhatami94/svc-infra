from __future__ import annotations

import sys
import types
from uuid import UUID

import pytest
from fastapi import APIRouter
from pydantic import BaseModel, SecretStr

import svc_infra.auth.users as users_mod


# -----------------------------
# Fakes used for monkeypatching
# -----------------------------
class FakeSQLAlchemyUserDatabase:
    def __init__(self, session, model):
        self.session = session
        self.model = model


class FakeJWTStrategy:
    def __init__(self, *, secret: str, lifetime_seconds: int):
        self.secret = secret
        self.lifetime_seconds = lifetime_seconds


class FakeFastAPIUsers:
    def __init__(self, get_user_manager, backends):
        self._get_user_manager = get_user_manager
        self._backends = backends

    def get_auth_router(self, backend, requires_verification: bool = False) -> APIRouter:
        router = APIRouter()
        router.prefix = "/__fake_auth_router__"
        return router

    def get_users_router(self, read, create, update) -> APIRouter:
        router = APIRouter()
        router.prefix = "/__fake_users_router__"
        return router


class FakeSettings:
    def __init__(self, secret: str, lifetime: int):
        # matches what your factory accesses
        self.jwt_secret = SecretStr(secret)
        self.jwt_lifetime_seconds = lifetime


# minimal dummy models/schemas
class UserModel:
    id: UUID


class UserRead(BaseModel):
    id: str


class UserCreate(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    email: str | None = None


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    """
    Patch:
      - fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase  -> FakeSQLAlchemyUserDatabase
      - JWTStrategy                                         -> FakeJWTStrategy
      - FastAPIUsers                                        -> FakeFastAPIUsers
    """
    # Provide a fake importable module for fastapi_users_db_sqlalchemy
    fake_db_mod = types.SimpleNamespace(SQLAlchemyUserDatabase=FakeSQLAlchemyUserDatabase)
    monkeypatch.setitem(sys.modules, "fastapi_users_db_sqlalchemy", fake_db_mod)

    # Replace symbols used by the factory
    monkeypatch.setattr(users_mod, "JWTStrategy", FakeJWTStrategy, raising=True)
    monkeypatch.setattr(users_mod, "FastAPIUsers", FakeFastAPIUsers, raising=True)
    yield


def _set_settings(monkeypatch, secret: str, lifetime: int):
    """Patch get_auth_settings() in the factory module to return desired values."""
    monkeypatch.setattr(users_mod, "get_auth_settings", lambda: FakeSettings(secret, lifetime), raising=True)


def test_factory_returns_objects_and_respects_prefix(monkeypatch):
    _set_settings(monkeypatch, secret="sekret", lifetime=3600)

    auth_prefix = "/authz"
    fastapi_users, backend, auth_router, users_router, get_strategy = users_mod.get_fastapi_users(
        user_model=UserModel,
        user_schema_read=UserRead,
        user_schema_create=UserCreate,
        user_schema_update=UserUpdate,
        auth_prefix=auth_prefix,
    )

    assert isinstance(auth_router, APIRouter)
    assert isinstance(users_router, APIRouter)
    assert callable(get_strategy)

    assert getattr(auth_router, "prefix", "") == "/__fake_auth_router__"
    assert getattr(users_router, "prefix", "") == "/__fake_users_router__"

    assert backend.name == "jwt"

    from fastapi_users.authentication import BearerTransport

    transport = backend.transport
    # Always ensure it's the expected transport type
    assert isinstance(transport, BearerTransport)

    # Try to validate the configured path if the version exposes it
    resolved = None
    for attr in ("tokenUrl", "token_url", "login_path"):
        if hasattr(transport, attr):
            resolved = getattr(transport, attr)
            break
    if resolved is None and hasattr(transport, "get_login_path") and callable(transport.get_login_path):
        resolved = transport.get_login_path()

    # If the path is introspectable, verify it; otherwise accept type check only
    if resolved is not None:
        assert resolved == f"{auth_prefix}/jwt/login"


def test_get_jwt_strategy_uses_settings_at_call_time(monkeypatch):
    _set_settings(monkeypatch, secret="one", lifetime=10)
    *_, get_strategy = users_mod.get_fastapi_users(
        user_model=UserModel,
        user_schema_read=UserRead,
        user_schema_create=UserCreate,
        user_schema_update=UserUpdate,
    )
    s1 = get_strategy()
    assert isinstance(s1, FakeJWTStrategy)
    assert s1.secret == "one"
    assert s1.lifetime_seconds == 10

    _set_settings(monkeypatch, secret="two", lifetime=20)
    s2 = get_strategy()
    assert isinstance(s2, FakeJWTStrategy)
    assert s2.secret == "two"
    assert s2.lifetime_seconds == 20


def test_sqlalchemy_user_database_is_wired(monkeypatch):
    _set_settings(monkeypatch, secret="sekret", lifetime=3600)
    fastapi_users, backend, auth_router, users_router, get_strategy = users_mod.get_fastapi_users(
        user_model=UserModel,
        user_schema_read=UserRead,
        user_schema_create=UserCreate,
        user_schema_update=UserUpdate,
    )

    # Sanity: DI callable present and strategy is our fake
    get_user_manager = fastapi_users._get_user_manager  # exposed by FakeFastAPIUsers
    assert callable(get_user_manager)

    strat = get_strategy()
    assert isinstance(strat, FakeJWTStrategy)