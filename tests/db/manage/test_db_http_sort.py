from __future__ import annotations

from svc_infra.api.fastapi.db.sql import build_order_by


class _Col:
    def __init__(self, name: str):
        self.name = name

    def asc(self):
        return (self.name, "asc")

    def desc(self):
        return (self.name, "desc")


class _Model:
    created_at = _Col("created_at")
    name = _Col("name")


def test_build_order_by_basic():
    sort = ["-created_at", "name", "unknown"]
    result = build_order_by(_Model, sort)
    # should ignore unknown, produce tuples in order
    assert result == [("created_at", "desc"), ("name", "asc")]
