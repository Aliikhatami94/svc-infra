from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from svc_infra.cache.ttl import TTL_DEFAULT, TTL_LONG, TTL_SHORT, get_ttl, validate_ttl


def test_validate_ttl_uses_defaults_for_none_and_negative(monkeypatch):
    # None → default
    assert validate_ttl(None) == TTL_DEFAULT
    # negative → default
    assert validate_ttl(-5) == TTL_DEFAULT
    # valid → as-is
    assert validate_ttl(60) == 60


def test_get_ttl_map_values(monkeypatch):
    assert get_ttl("default") == TTL_DEFAULT
    assert get_ttl("short") == TTL_SHORT
    assert get_ttl("long") == TTL_LONG
    # case-insensitive
    assert get_ttl("ShOrT") == TTL_SHORT
    # invalid → None
    assert get_ttl("nope") is None


def test_generate_key_variants_with_and_without_namespace(mocker):
    # Force a namespace from backend alias
    mocker.patch("svc_infra.cache.recache._alias", return_value="ns:v1")

    from svc_infra.cache.recache import generate_key_variants

    variants = generate_key_variants("user:{user_id}:profile", {"user_id": 7})
    # Should include both namespaced and raw versions without dupes
    assert variants == ["ns:v1:user:7:profile", "user:7:profile"]


@pytest.mark.asyncio
async def test_execute_recache_deletes_key_variants_and_calls_getter(mocker):
    # Patch namespace and cache.delete
    mocker.patch("svc_infra.cache.recache._alias", return_value="ns:v1")

    deleted = []

    async def _delete(key):
        deleted.append(key)

    mocker.patch("svc_infra.cache.recache._cache.delete", side_effect=_delete)

    # Getter to be warmed (must declare parameters so call_kwargs are populated)
    called = {"n": 0}

    async def getter(*, user_id: int):  # pragma: no cover - trivial
        called["n"] += 1
        return {"id": user_id}

    from svc_infra.cache.recache import RecachePlan, execute_recache

    plan = RecachePlan(getter=getter, include=["user_id"], key="user:{user_id}:profile")

    await execute_recache([plan], user_id=42, other="x")

    # Both namespaced and raw keys attempted
    assert "ns:v1:user:42:profile" in deleted
    assert "user:42:profile" in deleted
    assert called["n"] == 1
