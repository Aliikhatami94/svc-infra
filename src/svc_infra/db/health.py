from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def db_healthcheck(session: AsyncSession) -> bool:
    try:
        await session.execute(text("select 1"))
        return True
    except Exception:
        return False

