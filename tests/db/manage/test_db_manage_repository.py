from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from svc_infra.api.fastapi.db.sql import SqlRepository
import svc_infra.api.fastapi.db.sql.repository as repo_mod


@pytest.fixture(autouse=True)
def _sqlite_patch_now(monkeypatch):
    # SQLite doesn't have NOW(); map to CURRENT_TIMESTAMP for tests
    monkeypatch.setattr(repo_mod.func, "now", lambda: func.current_timestamp())


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items_repo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class SoftItem(Base):
    __tablename__ = "soft_items_repo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:  # keep one session per test
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_crud_hard_delete(session: AsyncSession):
    repo = SqlRepository(model=Item)

    # create
    a = await repo.create(session, {"name": "alpha"})
    b = await repo.create(session, {"name": "beta"})
    assert a.id != b.id and a.name == "alpha"

    # list ordered by name asc
    rows = await repo.list(session, limit=10, offset=0, order_by=[Item.name.asc()])
    assert [r.name for r in rows] == ["alpha", "beta"]

    # count
    assert await repo.count(session) == 2

    # get
    got = await repo.get(session, a.id)
    assert got is not None and got.id == a.id

    # update respects immutable fields (id)
    updated = await repo.update(session, a.id, {"id": 999, "name": "ALPHA"})
    assert updated is not None and updated.id == a.id and updated.name == "ALPHA"

    # delete existing
    ok = await repo.delete(session, a.id)
    assert ok is True
    assert await repo.get(session, a.id) is None

    # delete missing
    assert await repo.delete(session, 123456) is False


@pytest.mark.asyncio
async def test_repository_soft_delete_timestamp_only(session: AsyncSession):
    repo = SqlRepository(model=SoftItem, soft_delete=True)

    s1 = await repo.create(session, {"name": "x"})
    s2 = await repo.create(session, {"name": "y"})

    # visible before delete
    assert await repo.count(session) == 2

    # delete one -> marks deleted_at
    ok = await repo.delete(session, s1.id)
    assert ok is True

    # not visible in list/count/get
    assert await repo.count(session) == 1
    rows = await repo.list(session, limit=10, offset=0)
    assert len(rows) == 1 and rows[0].id == s2.id
    assert await repo.get(session, s1.id) is None

    # row is still present in table with deleted_at set
    # (raw query)
    raw = (await session.execute(select(SoftItem).where(SoftItem.id == s1.id))).scalar_one()
    assert raw.deleted_at is not None


@pytest.mark.asyncio
async def test_repository_soft_delete_with_flag(session: AsyncSession):
    repo = SqlRepository(model=SoftItem, soft_delete=True, soft_delete_flag_field="active")

    s1 = await repo.create(session, {"name": "x"})
    _ = await repo.create(session, {"name": "y"})

    ok = await repo.delete(session, s1.id)
    assert ok is True

    # list/count/get respect both deleted_at and active flag
    assert await repo.count(session) == 1
    assert await repo.get(session, s1.id) is None

    # raw fetch shows active = False
    raw = (await session.execute(select(SoftItem).where(SoftItem.id == s1.id))).scalar_one()
    assert raw.active is False and raw.deleted_at is not None


@pytest.mark.asyncio
async def test_repository_search_and_count_filtered(session: AsyncSession):
    repo = SqlRepository(model=Item)
    _ = await repo.create(session, {"name": "Alpha"})
    _ = await repo.create(session, {"name": "beta"})
    _ = await repo.create(session, {"name": "ALP"})

    rows = await repo.search(session, q="al", fields=["name"], limit=10, offset=0, order_by=[Item.name.asc()])
    assert [r.name for r in rows] == ["ALP", "Alpha"]

    total = await repo.count_filtered(session, q="AL", fields=["name"])
    assert total == 2


@pytest.mark.asyncio
async def test_repository_exists_and_ordering_none(session: AsyncSession):
    repo = SqlRepository(model=Item)
    _ = await repo.create(session, {"name": "c"})
    _ = await repo.create(session, {"name": "d"})

    exists = await repo.exists(session, where=[Item.name == "d"])  # type: ignore[comparison-overlap]
    assert exists is True

    not_exists = await repo.exists(session, where=[Item.name == "zzz"])  # type: ignore[comparison-overlap]
    assert not_exists is False

    # order_by None
    rows = await repo.list(session, limit=10, offset=0, order_by=None)
    assert len(rows) == 2
