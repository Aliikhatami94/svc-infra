from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from svc_infra.api.fastapi.tenancy.add import add_tenancy
from svc_infra.api.fastapi.tenancy.context import resolve_tenant_id, set_tenant_resolver


@pytest.mark.asyncio
async def test_add_tenancy_sets_resolver():
    app = FastAPI()

    async def resolver(request: Request, identity, header):
        return "tenant_from_helper"

    try:
        add_tenancy(app, resolver=resolver)
        tid = await resolve_tenant_id(_fake_request())
        assert tid == "tenant_from_helper"
    finally:
        set_tenant_resolver(None)


def _fake_request():
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    return Request(scope)
