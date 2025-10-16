from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from svc_infra.db.sql.repository import SqlRepository

if TYPE_CHECKING:
    # TYPE_CHECKING prevents a runtime import; only used by type checkers
    from svc_infra.db.sql.service import SqlService


@dataclass
class SqlResource:
    model: type[object]
    prefix: str
    tags: Optional[list[str]] = None

    id_attr: str = "id"
    soft_delete: bool = False
    search_fields: Optional[list[str]] = None
    ordering_default: Optional[str] = None
    allowed_order_fields: Optional[list[str]] = None

    read_schema: Optional[type] = None
    create_schema: Optional[type] = None
    update_schema: Optional[type] = None

    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None

    create_exclude: tuple[str, ...] = ("id",)

    # Only a type reference; no runtime dependency on FastAPI layer
    service_factory: Optional[Callable[[SqlRepository], "SqlService"]] = None

    # Tenancy
    tenant_field: Optional[str] = (
        None  # when set, CRUD router will require TenantId and scope by field
    )
