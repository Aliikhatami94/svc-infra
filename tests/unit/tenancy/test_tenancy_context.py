from __future__ import annotations

import types

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from svc_infra.api.fastapi.tenancy.context import (
    require_tenant_id,
    resolve_tenant_id,
    set_tenant_resolver,
)


def _request(*, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_resolve_tenant_from_identity_user():
    user = types.SimpleNamespace(tenant_id="tenant_user")
    principal = types.SimpleNamespace(user=user, api_key=None)

    tenant_id = await resolve_tenant_id(_request(), identity=principal)

    assert tenant_id == "tenant_user"


@pytest.mark.asyncio
async def test_override_hook_takes_precedence():
    calls: list[tuple[Request, object | None, str | None]] = []

    async def _override(
        request: Request, identity: object | None, header: str | None
    ) -> str:
        calls.append((request, identity, header))
        return "tenant_override"

    set_tenant_resolver(_override)
    try:
        tenant_id = await resolve_tenant_id(_request())
    finally:
        set_tenant_resolver(None)

    assert calls, "override hook should be invoked"
    assert tenant_id == "tenant_override"


@pytest.mark.asyncio
async def test_override_can_defer_to_default_flow():
    calls: list[tuple[Request, object | None, str | None]] = []

    def _override(
        request: Request, identity: object | None, header: str | None
    ) -> None:
        calls.append((request, identity, header))
        return None

    set_tenant_resolver(_override)
    try:
        tenant_id = await resolve_tenant_id(_request(), tenant_header="tenant_header")
    finally:
        set_tenant_resolver(None)

    assert calls, "override should be called even when deferring"
    assert tenant_id == "tenant_header"


@pytest.mark.asyncio
async def test_resolve_tenant_from_principal_api_key():
    api_key = types.SimpleNamespace(tenant_id="tenant_api")
    principal = types.SimpleNamespace(user=None, api_key=api_key)

    tenant_id = await resolve_tenant_id(_request(), identity=principal)

    assert tenant_id == "tenant_api"


@pytest.mark.asyncio
async def test_resolve_tenant_from_header():
    tenant_id = await resolve_tenant_id(_request(), tenant_header="tenant_header")

    assert tenant_id == "tenant_header"


@pytest.mark.asyncio
async def test_resolve_tenant_from_request_state():
    request = _request()
    request.state.tenant_id = "tenant_state"

    tenant_id = await resolve_tenant_id(request)

    assert tenant_id == "tenant_state"


@pytest.mark.asyncio
async def test_missing_tenant_context_raises():
    with pytest.raises(HTTPException) as exc:
        await require_tenant_id(tenant_id=None)  # type: ignore[arg-type]

    assert exc.value.status_code == 400
    assert exc.value.detail == "tenant_context_missing"
