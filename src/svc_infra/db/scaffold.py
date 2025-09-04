from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Dict, Any, Optional

# Reuse the same helpers you used for auth scaffolds --------------------------
# (inline minimal fallbacks in case you prefer this to be fully standalone)
def _normalize_dir(p: Path | str) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (Path.cwd() / p).resolve()

def _write(dest: Path, content: str, overwrite: bool) -> Dict[str, Any]:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {"path": str(dest), "action": "skipped", "reason": "exists"}
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "action": "wrote"}


# -------------------- default inlined templates (small & generic) --------------------

_DEFAULT_MODELS_TPL = Template(
    """from __future__ import annotations
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Boolean, DateTime, JSON, Text, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableDict

from svc_infra.db.base import ModelBase


class ${Entity}(ModelBase):
    __tablename__ = "${table_name}"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

$tenant_field$soft_delete_field    extra: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)

    # auditing (DB-side timestamps)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

$constraints    def __repr__(self) -> str:
        return f"<${Entity} id={self.id} name={self.name!r}>"

$indexes"""
)

_DEFAULT_SCHEMAS_TPL = Template(
    """from __future__ import annotations
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime


class ${Entity}Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    name: str
    description: Optional[str] = None
$tenant_field    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class ${Entity}Read(${Entity}Base, Timestamped):
    id: str


class ${Entity}Create(BaseModel):
    name: str
    description: Optional[str] = None
$tenant_field_create    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class ${Entity}Update(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
$tenant_field_update    is_active: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None
"""
)


# -------------------- public API --------------------

def scaffold_entity_core(
        *,
        models_dir: Path | str,
        schemas_dir: Path | str,
        entity_name: str = "Item",
        table_name: Optional[str] = None,
        include_tenant: bool = True,
        include_soft_delete: bool = False,
        overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Create minimal model + schemas for a new domain entity.

    Examples:
        >>> scaffold_entity_core(models_dir="app/models", schemas_dir="app/schemas", entity_name="Project")
        >>> scaffold_entity_core(models_dir="app/models", schemas_dir="app/schemas", entity_name="Note", include_tenant=False)

    Notes:
        - Uses svc_infra.db.base.ModelBase for discovery/migrations.
        - Columns: id (UUID pk), name, description, extra (JSON), is_active (+ optional tenant_id, deleted_at).
        - Adds audit timestamps (created_at, updated_at).
    """
    models_dir = _normalize_dir(models_dir)
    schemas_dir = _normalize_dir(schemas_dir)

    ent = _normalize_entity_name(entity_name)
    tbl = table_name or _suggest_table_name(ent)

    # pieces for optional fields/constraints/indexes
    tenant_model_field = (
        '    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)\n'
        if include_tenant else ""
    )
    soft_delete_model_field = (
        '    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n'
        '    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))\n'
        if include_soft_delete else
        '    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n'
    )

    constraints = ""
    if include_tenant:
        # nice starter: keep names unique per-tenant; easy to delete if not wanted
        constraints = '    __table_args__ = (\n' \
                      '        UniqueConstraint("tenant_id", "name", name=f"uq_' + tbl + '_tenant_name"),\n' \
                                                                                         '    )\n'

    indexes = ""
    if include_tenant:
        indexes = f'Index("ix_{tbl}_tenant_id", {ent}.tenant_id)\n'

    models_txt = _DEFAULT_MODELS_TPL.substitute(
        Entity=ent,
        table_name=tbl,
        tenant_field=tenant_model_field,
        soft_delete_field=soft_delete_model_field,
        constraints=constraints,
        indexes=indexes,
    )

    tenant_schema_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
    tenant_schema_field_create = tenant_schema_field
    tenant_schema_field_update = "    tenant_id: Optional[str] = None\n" if include_tenant else ""

    schemas_txt = _DEFAULT_SCHEMAS_TPL.substitute(
        Entity=ent,
        tenant_field=tenant_schema_field,
        tenant_field_create=tenant_schema_field_create,
        tenant_field_update=tenant_schema_field_update,
    )

    models_res = _write(models_dir / f"{_snake(ent)}.py", models_txt, overwrite)
    schemas_res = _write(schemas_dir / f"{_snake(ent)}.py", schemas_txt, overwrite)
    return {
        "status": "ok",
        "results": {"models": models_res, "schemas": schemas_res},
    }


def scaffold_entity_models_core(
        *,
        dest_dir: Path | str,
        entity_name: str = "Item",
        table_name: Optional[str] = None,
        include_tenant: bool = True,
        include_soft_delete: bool = False,
        overwrite: bool = False,
) -> Dict[str, Any]:
    """Create only the model file for a new entity (see scaffold_entity_core for args)."""
    tmp = scaffold_entity_core(
        models_dir=dest_dir,
        schemas_dir=dest_dir,  # throwaway; we'll ignore output
        entity_name=entity_name,
        table_name=table_name,
        include_tenant=include_tenant,
        include_soft_delete=include_soft_delete,
        overwrite=overwrite,
    )
    return {"status": "ok", "result": tmp["results"]["models"]}


def scaffold_entity_schemas_core(
        *,
        dest_dir: Path | str,
        entity_name: str = "Item",
        include_tenant: bool = True,
        overwrite: bool = False,
) -> Dict[str, Any]:
    """Create only the schemas file for a new entity (see scaffold_entity_core for args)."""
    # Render just schemas using same substitution logic
    ent = _normalize_entity_name(entity_name)
    tenant_schema_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
    schemas_txt = _DEFAULT_SCHEMAS_TPL.substitute(
        Entity=ent,
        tenant_field=tenant_schema_field,
        tenant_field_create=tenant_schema_field,
        tenant_field_update=tenant_schema_field,
    )
    dest_dir = _normalize_dir(dest_dir)
    res = _write(dest_dir / f"{_snake(ent)}.py", schemas_txt, overwrite)
    return {"status": "ok", "result": res}


# -------------------- tiny utilities --------------------

def _normalize_entity_name(name: str) -> str:
    # PascalCase the given name (cheap & cheerful)
    parts = [p for p in _snake(name).split("_") if p]
    return "".join(p.capitalize() for p in parts) or "Item"

def _snake(name: str) -> str:
    import re
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\\1_\\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\\1_\\2", s1)
    return re.sub("[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")

def _suggest_table_name(entity_pascal: str) -> str:
    # simple pluralizer fallback: add "s" — devs can rename later
    base = _snake(entity_pascal)
    return base + "s" if not base.endswith("s") else base