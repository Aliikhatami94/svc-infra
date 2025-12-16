from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.security import Principal, _current_principal
from svc_infra.documents import add_documents


@pytest.mark.asyncio
async def test_add_documents_upload_accepts_multipart_file() -> None:
    app = FastAPI()

    # The documents router uses user_router(), so satisfy auth dependency.
    app.dependency_overrides[_current_principal] = lambda: Principal(user=Mock())

    add_documents(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/documents/upload",
            data={"user_id": "user_1", "category": "legal"},
            files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["user_id"] == "user_1"
    assert payload["filename"] == "test.txt"
    assert payload["content_type"] == "text/plain"
    assert payload["metadata"]["category"] == "legal"
