from __future__ import annotations

import pytest
from fastapi_users.authentication.strategy.jwt import JWTStrategy

from svc_infra.security.jwt_rotation import RotatingJWTStrategy


@pytest.mark.asyncio
async def test_rotating_jwt_strategy_accepts_old_secret():
    old_secret = "old-secret"
    new_secret = "new-secret"

    # Issue with old secret using base JWTStrategy
    issuer = JWTStrategy(
        secret=old_secret, lifetime_seconds=60, token_audience="fastapi-users:auth"
    )
    # Minimal dict-like user
    user = type("U", (), {"id": "user-1"})()
    token = await issuer.write_token(user)

    # Rotate: verify with rotating strategy having new + old
    rot = RotatingJWTStrategy(
        secret=new_secret,
        lifetime_seconds=60,
        old_secrets=[old_secret],
        token_audience="fastapi-users:auth",
    )
    claims = await rot.read_token(token, audience="fastapi-users:auth")
    assert claims is not None


@pytest.mark.asyncio
async def test_rotating_jwt_strategy_rejects_unrelated_secret():
    unrelated = "other-secret"
    new_secret = "new-secret"

    issuer = JWTStrategy(
        secret=unrelated, lifetime_seconds=60, token_audience="fastapi-users:auth"
    )
    user = type("U", (), {"id": "user-2"})()
    token = await issuer.write_token(user)

    rot = RotatingJWTStrategy(
        secret=new_secret,
        lifetime_seconds=60,
        old_secrets=["old-secret"],
        token_audience="fastapi-users:auth",
    )  # unrelated
    with pytest.raises(Exception):
        await rot.read_token(token)
