import pytest
from sqlalchemy import text

from svc_infra.api.fastapi.db.sql.session import dispose_session, get_session, initialize_session

# Skip test if aiosqlite is not installed (it's an optional dependency)
pytest.importorskip("aiosqlite")


@pytest.mark.asyncio
async def test_db_statement_timeout_env_smoke_on_sqlite(monkeypatch):
    # Set a small statement timeout; on SQLite this should be ignored without error.
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "5")

    # Initialize an in-memory SQLite async engine
    initialize_session("sqlite+aiosqlite://")

    try:
        agen = get_session()
        session = await agen.__anext__()
        try:
            res = await session.execute(text("SELECT 1"))
            # Basic smoke: result should be retrievable; behavior is a no-op under SQLite
            _ = res.scalar_one_or_none()  # type: ignore[attr-defined]
        finally:
            await agen.aclose()
    finally:
        await dispose_session()
