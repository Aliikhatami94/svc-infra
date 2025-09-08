from typing import Any, Optional, Type
from dataclasses import dataclass

@dataclass
class Resource:
    # Required
    model: type[object]
    prefix: str  # e.g. "/projects"

    # Optional FastAPI presentation
    tags: Optional[list[str]] = None

    # Optional overrides / knobs
    id_attr: str = "id"
    soft_delete: bool = False            # enables soft-delete endpoints if your model has deleted_at
    search_fields: Optional[list[str]] = None  # used by router_plus if implemented there
    ordering_default: Optional[str] = None
    allowed_order_fields: Optional[list[str]] = None  # expose to router

    # If you already have Pydantic classes, pass them here and we won't autogen
    read_schema: Optional[Type[Any]] = None
    create_schema: Optional[Type[Any]] = None
    update_schema: Optional[Type[Any]] = None

    # Autogen schema names (only used when the three above are None)
    read_name: Optional[str] = None
    create_name: Optional[str] = None
    update_name: Optional[str] = None

    # When autogenerating Create, exclude these model columns (e.g. "id", server defaults)
    create_exclude: tuple[str, ...] = ("id",)