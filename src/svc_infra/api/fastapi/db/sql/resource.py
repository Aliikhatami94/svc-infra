from dataclasses import dataclass
from typing import Any, Optional, Type, Callable

from .service import Service
from .repository import Repository

@dataclass
class Resource:
    model: type[object]
    prefix: str
    tags: Optional[list[str]] = None

    id_attr: str = "id"
    soft_delete: bool = False
    search_fields: Optional[list[str]] = None
    ordering_default: Optional[str] = None
    allowed_order_fields: Optional[list[str]] = None

    read_schema: Optional[Type[Any]] = None
    create_schema: Optional[Type[Any]] = None
    update_schema: Optional[Type[Any]] = None

    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None

    create_exclude: tuple[str, ...] = ("id",)

    # NEW – optional hook to build a custom Service
    service_factory: Optional[Callable[[Repository], Service]] = None