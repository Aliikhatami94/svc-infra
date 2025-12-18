# models/tasks.py
from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text, text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID
from svc_infra.db.sql.uniq import make_unique_sql_indexes
from svc_infra.db.sql.uniq_hooks import dedupe_sql_service

if TYPE_CHECKING:
    # only for type hints; avoids importing at runtime
    from svc_infra.db.sql.repository import SqlRepository

# ------------------------------ Model ------------------------------


class Task(ModelBase):
    __tablename__ = "tasks"

    # identity
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # misc (avoid attr name "metadata" clash)
    extra: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)

    # auditing (DB-side timestamps)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} name={self.name!r}>"


# --- Uniqueness policy --------------------------------------------------------
# Functional unique indexes (case-insensitive on "name"),
# optionally scoped by tenant if present.
for _ix in make_unique_sql_indexes(Task, unique_ci=["name"], tenant_field="tenant_id"):
    # Iterating registers them on the Table metadata (alembic/autogenerate will pick them up).
    pass

# ----------------------- Service factory (entity) -----------------------------

PreHook = Callable[[dict[str, Any]], dict[str, Any]]
ColumnSpec = str | Sequence[str]


def _map_entity_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Basic payload normalization common to most entities:
      - metadata (schema alias) -> extra (column)
      - normalize name (trim whitespace)
    Extend per-project via extra_pre_create/extra_pre_update in make_entity_service.
    """
    d = dict(data)
    if "metadata" in d:
        d["extra"] = d.pop("metadata")
    if "name" in d and isinstance(d["name"], str):
        d["name"] = d["name"].strip()
    return d


def _compose(*hooks: PreHook | None) -> PreHook:
    """Chain multiple pre-hooks left-to-right, skipping Nones."""

    def _runner(payload: dict[str, Any]) -> dict[str, Any]:
        out = payload
        for h in hooks:
            if h:
                out = h(out)
        return out

    return _runner


def create_entity_service(
    repo: SqlRepository,
    *,
    # Uniqueness defaults (match the indexes above)
    unique_ci: Iterable[ColumnSpec] = ("name",),
    tenant_field: str | None = "tenant_id",
    # Allow projects to extend behavior without writing a whole service
    extra_pre_create: PreHook | None = None,
    extra_pre_update: PreHook | None = None,
    # Optional: override 409 messages per-spec, e.g. {("name",): "Task name already exists."}
    messages: dict[tuple[str, ...], str] | None = None,
):
    """
    Build a generic entity Service that:
      • Normalizes payload (metadata→extra, trims name)
      • Enforces uniqueness via dedupe_sql_service (CI by default on 'name')
      • Returns 409 like: "Record with name='Foo' already exists."
      • Accepts extra pre-hooks for project-specific rules.
    """
    pre_create = _compose(_map_entity_fields, extra_pre_create)
    pre_update = _compose(_map_entity_fields, extra_pre_update)

    return dedupe_sql_service(
        repo,
        unique_ci=unique_ci,
        tenant_field=tenant_field,
        messages=messages,
        pre_create=pre_create,
        pre_update=pre_update,
    )
