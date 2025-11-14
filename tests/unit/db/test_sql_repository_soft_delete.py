from __future__ import annotations

import asyncio
from typing import Any

import pytest

from svc_infra.db.sql.repository import SqlRepository


class _Row:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
        self.deleted_at = None
        self.is_active = True


class _Model:
    def __init__(self):
        self._rows: list[_Row] = []

    id = type("Col", (), {"asc": lambda self: ("id", "asc"), "desc": lambda self: ("id", "desc")})()
    deleted_at = type("Col", (), {"is_": lambda self, v: ("deleted_at_is", v)})()
    is_active = type("Col", (), {"is_": lambda self, v: ("is_active_is", v)})()

    # mimic SQLAlchemy class_mapper columns
    @property
    def __mapper__(self):  # pragma: no cover - not actually used by our class_mapper stub
        return None


class _Session:
    def __init__(self, store: _Model):
        self.store = store

    async def execute(self, stmt):  # very simplified behavior
        class R:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                class S:
                    def __init__(self, rows):
                        self._rows = rows

                    def all(self):
                        return list(self._rows)

                    def first(self):
                        return self._rows[0] if self._rows else None

                return S(self._rows)

            def scalar_one(self):
                return len(self._rows)

            def first(self):
                return self._rows[0] if self._rows else None

        # naive filtering: if selecting, return non-deleted rows
        rows = [r for r in self.store._rows if r.deleted_at is None and r.is_active]
        return R(rows)

    async def get(self, model, pk):
        for r in self.store._rows:
            if r.id == pk:
                return r
        return None

    def add(self, obj):
        self.store._rows.append(obj)

    async def flush(self):
        return

    async def refresh(self, obj):
        return

    def delete(self, obj):
        self.store._rows.remove(obj)


def _class_mapper_stub(model):
    # returns object with .columns like keys of the row
    class C:
        columns = type(
            "Cols",
            (),
            {
                "__iter__": lambda self: iter(
                    [type("K", (), {"key": k})() for k in ["id", "name", "deleted_at", "is_active"]]
                )
            },
        )()

    return C()


@pytest.mark.asyncio
async def test_soft_delete_timestamps_and_flag(monkeypatch):
    # patch class_mapper used by SqlRepository
    monkeypatch.setattr("svc_infra.db.sql.repository.class_mapper", _class_mapper_stub)

    model = _Model()
    repo = SqlRepository(
        model=_Row,
        soft_delete=True,
        soft_delete_field="deleted_at",
        soft_delete_flag_field="is_active",
    )
    sess = _Session(model)

    # create two rows
    await repo.create(sess, {"id": 1, "name": "A"})
    await repo.create(sess, {"id": 2, "name": "B"})

    # soft delete one
    ok = await repo.delete(sess, 1)
    assert ok is True
    row = await sess.get(_Row, 1)
    assert row.deleted_at is not None
    assert row.is_active is False

    # verify only non-deleted remains effectively listed (simulate by checking store)
    ids = [r.id for r in model._rows if r.deleted_at is None and r.is_active]
    assert ids == [2]
