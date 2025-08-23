import asyncio
import uuid

import pytest

from svc_infra.db import (
    Base,
    UUIDMixin,
    DBSettings,
    DBEngine,
    UnitOfWork,
    db_healthcheck,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import text


class User(UUIDMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]


@pytest.mark.asyncio
async def test_repo_crud_and_healthcheck():
    # Use in-memory SQLite for speed
    settings = DBSettings(database_url="sqlite+aiosqlite:///:memory:")
    engine = DBEngine(settings)

    # Create schema using async DDL (avoid greenlet dependency)
    async with engine.session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE users (
                    id CHAR(36) PRIMARY KEY,
                    email VARCHAR NOT NULL UNIQUE,
                    name VARCHAR NOT NULL
                )
                """
            )
        )
        await session.commit()

    # Healthcheck should pass
    async with engine.session() as session:
        assert await db_healthcheck(session) is True

    # CRUD via UnitOfWork and Repository
    async with UnitOfWork(engine) as uow:
        repo = uow.repo(User)
        # create
        u = await repo.create(email="alice@example.com", name="Alice")
        assert isinstance(u.id, uuid.UUID)

    # Verify list and get in a new uow (commit happened)
    async with UnitOfWork(engine) as uow:
        repo = uow.repo(User)
        users = await repo.list()
        assert len(users) == 1
        got = await repo.get(users[0].id)
        assert got is not None and got.email == "alice@example.com"
        # update
        updated = await repo.update(got.id, name="Alice Updated")
        assert updated is not None and updated.name == "Alice Updated"

    # Deletion
    async with UnitOfWork(engine) as uow:
        repo = uow.repo(User)
        cnt = await repo.delete((await repo.list())[0].id)
        assert cnt == 1

    # No users left
    async with UnitOfWork(engine) as uow:
        repo = uow.repo(User)
        users = await repo.list()
        assert users == []
