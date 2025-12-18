from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from svc_infra.db.sql.repository import SqlRepository

if TYPE_CHECKING:
    # TYPE_CHECKING prevents a runtime import; only used by type checkers
    from svc_infra.db.sql.service import SqlService


@dataclass
class SqlResource:
    model: type[object]
    prefix: str
    tags: list[str] | None = None

    id_attr: str = "id"
    soft_delete: bool = False
    search_fields: list[str] | None = None
    ordering_default: str | None = None
    allowed_order_fields: list[str] | None = None

    read_schema: type | None = None
    create_schema: type | None = None
    update_schema: type | None = None

    read_name: str | None = None
    create_name: str | None = None
    update_name: str | None = None

    create_exclude: tuple[str, ...] = ("id",)

    # Only a type reference; no runtime dependency on FastAPI layer
    service_factory: Callable[[SqlRepository], SqlService] | None = None

    # Tenancy
    tenant_field: str | None = (
        None  # when set, CRUD router will require TenantId and scope by field
    )
