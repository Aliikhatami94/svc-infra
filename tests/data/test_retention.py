from __future__ import annotations

import pytest

from svc_infra.data.retention import RetentionPolicy, run_retention_purge

pytestmark = pytest.mark.data_lifecycle


class FakeCol:
    def __init__(self, name: str):
        self.name = name

    def __le__(self, other):  # support created_at <= cutoff
        return (self.name, "<=", other)


class FakeModel:
    created_at = FakeCol("created_at")
    deleted_at = FakeCol("deleted_at")

    @staticmethod
    def update():
        class _U:
            def __init__(self):
                self._where = []

            def where(self, *conds):
                self._where.extend(conds)
                return self

            def values(self, mapping):
                self._values = mapping
                return ("update", tuple(self._where), mapping)

        return _U()

    @staticmethod
    def delete():
        class _D:
            def __init__(self):
                self._where = []

            def where(self, *conds):
                self._where.extend(conds)
                return ("delete", tuple(self._where))

        return _D()


class FakeSession:
    def __init__(self):
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)

        class R:
            rowcount = 3

        return R()


@pytest.mark.asyncio
async def test_run_retention_soft_delete():
    sess = FakeSession()
    pol = RetentionPolicy(
        name="demo", model=FakeModel, older_than_days=7, soft_delete_field="deleted_at"
    )
    total = await run_retention_purge(sess, [pol])
    assert total == 3
    stmt = sess.executed[0]
    assert isinstance(stmt, tuple) and stmt[0] == "update"
    # Ensure cutoff condition present
    conds = stmt[1]
    assert any(c[0] == "created_at" and c[1] == "<=" for c in conds)


@pytest.mark.asyncio
async def test_run_retention_hard_delete():
    sess = FakeSession()
    pol = RetentionPolicy(
        name="demo", model=FakeModel, older_than_days=30, soft_delete_field=None, hard_delete=True
    )
    total = await run_retention_purge(sess, [pol])
    assert total == 3
    stmt = sess.executed[0]
    assert isinstance(stmt, tuple) and stmt[0] == "delete"
