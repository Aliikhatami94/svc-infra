from __future__ import annotations

import types

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from svc_infra.api.fastapi.apf_payments.router import (
    get_service,
    resolve_payments_tenant_id,
    set_payments_tenant_resolver,
)
from svc_infra.api.fastapi.auth.security import Principal


class _DummySession:
    async def flush(self) -> None:  # pragma: no cover - not used in tests
        return None


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
async def test_resolve_tenant_from_principal_user():
    user = types.SimpleNamespace(tenant_id="tenant_user")
    principal = Principal(user=user, scopes=[], via="jwt")

    tenant_id = await resolve_payments_tenant_id(_request(), identity=principal)
    service = await get_service(session=_DummySession(), tenant_id=tenant_id)

    assert service.tenant_id == "tenant_user"


@pytest.mark.asyncio
async def test_override_hook_takes_precedence():
    override_calls: list[tuple[Request, Principal | None, str | None]] = []

    async def _override(request: Request, identity: Principal | None, header: str | None) -> str:
        override_calls.append((request, identity, header))
        return "tenant_override"

    set_payments_tenant_resolver(_override)
    try:
        tenant_id = await resolve_payments_tenant_id(_request())
    finally:
        set_payments_tenant_resolver(None)

    assert override_calls, "override hook should be invoked"
    assert tenant_id == "tenant_override"

    service = await get_service(session=_DummySession(), tenant_id=tenant_id)
    assert service.tenant_id == "tenant_override"


@pytest.mark.asyncio
async def test_async_override_hook_supported():
    calls: list[tuple[Request, Principal | None, str | None]] = []

    async def _override(request: Request, identity: Principal | None, header: str | None) -> str:
        calls.append((request, identity, header))
        return "tenant_async"

    set_payments_tenant_resolver(_override)
    try:
        tenant_id = await resolve_payments_tenant_id(_request())
    finally:
        set_payments_tenant_resolver(None)

    assert calls, "async override should be invoked"
    assert tenant_id == "tenant_async"

    service = await get_service(session=_DummySession(), tenant_id=tenant_id)
    assert service.tenant_id == "tenant_async"


@pytest.mark.asyncio
async def test_override_can_defer_to_default_flow():
    override_calls: list[tuple[Request, Principal | None, str | None]] = []

    def _override(request: Request, identity: Principal | None, header: str | None) -> None:
        override_calls.append((request, identity, header))
        return None

    set_payments_tenant_resolver(_override)
    try:
        tenant_id = await resolve_payments_tenant_id(_request(), tenant_header="tenant_header")
    finally:
        set_payments_tenant_resolver(None)

    assert override_calls, "override should be called even when deferring"
    assert tenant_id == "tenant_header"


@pytest.mark.asyncio
async def test_resolve_tenant_from_principal_api_key():
    api_key = types.SimpleNamespace(tenant_id="tenant_api")
    principal = Principal(user=None, scopes=[], via="api_key", api_key=api_key)

    tenant_id = await resolve_payments_tenant_id(_request(), identity=principal)

    assert tenant_id == "tenant_api"


@pytest.mark.asyncio
async def test_resolve_tenant_from_header():
    tenant_id = await resolve_payments_tenant_id(_request(), tenant_header="tenant_header")

    assert tenant_id == "tenant_header"


@pytest.mark.asyncio
async def test_resolve_tenant_from_request_state():
    request = _request()
    request.state.tenant_id = "tenant_state"

    tenant_id = await resolve_payments_tenant_id(request)

    assert tenant_id == "tenant_state"


@pytest.mark.asyncio
async def test_missing_tenant_context_raises():
    with pytest.raises(HTTPException) as exc:
        await resolve_payments_tenant_id(_request())

    assert exc.value.status_code == 400
    assert exc.value.detail == "tenant_context_missing"
