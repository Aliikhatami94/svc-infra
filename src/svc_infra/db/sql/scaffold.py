from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from svc_infra.db.utils import normalize_dir, pascal, plural_snake, snake
from svc_infra.utils import ensure_init_py, render_template, write

# ---------------- helpers ----------------

_INIT_CONTENT_PAIRED = 'from . import models, schemas\n\n__all__ = ["models", "schemas"]\n'
_INIT_CONTENT_MINIMAL = "# package marker; add explicit exports here if desired\n"


def _ensure_init_py(dir_path: Path, overwrite: bool, paired: bool) -> Dict[str, Any]:
    """Create __init__.py; paired=True writes models/schemas re-exports, otherwise minimal."""
    content = _INIT_CONTENT_PAIRED if paired else _INIT_CONTENT_MINIMAL
    return ensure_init_py(dir_path, overwrite, paired, content)


# ---------------- unified public API ----------------
# kind: "entity" (generic) or "auth" (specialized templates)

Kind = Literal["entity", "auth"]


def scaffold_core(
    *,
    models_dir: Path | str,
    schemas_dir: Path | str,
    kind: Kind = "entity",
    entity_name: str = "Item",
    table_name: Optional[str] = None,
    include_tenant: bool = True,
    include_soft_delete: bool = False,
    overwrite: bool = False,
    same_dir: bool = False,
    models_filename: Optional[str] = None,
    schemas_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create starter model + schema files.

    Filenames:
      - same_dir=True  -> models.py + schemas.py (paired).
      - same_dir=False -> defaults to <snake(entity)>.py in each dir, unless you pass
                          --models-filename / --schemas-filename.
    """
    models_dir = normalize_dir(models_dir)
    schemas_dir = normalize_dir(models_dir if same_dir else schemas_dir)

    # content per kind
    if kind == "auth":
        auth_ent = pascal(entity_name or "User")
        env_tbl = (
            os.getenv("AUTH_TABLE_NAME")
            or os.getenv("SVC_INFRA_AUTH_TABLE")
            or os.getenv("APF_AUTH_TABLE_NAME")
        )
        auth_tbl = (table_name or env_tbl or plural_snake(auth_ent)).strip()

        models_txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.auth",
            name="models.py.tmpl",
            subs={"AuthEntity": auth_ent, "auth_table_name": auth_tbl},
        )
        schemas_txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.auth",
            name="schemas.py.tmpl",
            subs={"AuthEntity": auth_ent},
        )
    else:
        ent = pascal(entity_name)
        tbl = table_name or plural_snake(ent)

        tenant_model_field = (
            "    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)\n"
            if include_tenant
            else ""
        )
        soft_delete_model_field = (
            "    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n"
            "    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))\n"
            if include_soft_delete
            else "    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n"
        )

        tenant_arg = ', tenant_field="tenant_id"' if include_tenant else ""
        tenant_default = '"tenant_id"' if include_tenant else "None"

        models_txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.entity",
            name="models.py.tmpl",
            subs={
                "Entity": ent,
                "table_name": tbl,
                "tenant_field": tenant_model_field,
                "soft_delete_field": soft_delete_model_field,
                "tenant_arg": tenant_arg,
                "tenant_default": tenant_default,
            },
        )

        tenant_schema_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
        schemas_txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.entity",
            name="schemas.py.tmpl",
            subs={
                "Entity": ent,
                "tenant_field": tenant_schema_field,
                "tenant_field_create": tenant_schema_field,
                "tenant_field_update": tenant_schema_field,
            },
        )

    # filenames
    if same_dir:
        models_path = models_dir / "models.py"
        schemas_path = schemas_dir / "schemas.py"
    else:
        default_stub = snake(entity_name)
        models_name = models_filename or f"{default_stub}.py"
        schemas_name = schemas_filename or f"{default_stub}.py"
        models_path = models_dir / models_name
        schemas_path = schemas_dir / schemas_name

    # write
    models_res = write(models_path, models_txt, overwrite)
    schemas_res = write(schemas_path, schemas_txt, overwrite)

    # __init__ files
    init_results = []
    init_results.append(_ensure_init_py(models_dir, overwrite, paired=same_dir))
    if schemas_dir != models_dir:
        init_results.append(_ensure_init_py(schemas_dir, overwrite, paired=False))

    return {
        "status": "ok",
        "results": {
            "models": models_res,
            "schemas": schemas_res,
            "inits": init_results,
        },
    }


def scaffold_models_core(
    *,
    dest_dir: Path | str,
    kind: Kind = "entity",
    entity_name: str = "Item",
    table_name: Optional[str] = None,
    include_tenant: bool = True,
    include_soft_delete: bool = False,
    overwrite: bool = False,
    models_filename: Optional[str] = None,  # <--- NEW
) -> Dict[str, Any]:
    """Create only a model file (defaults to <snake(entity)>.py unless models_filename is provided)."""
    dest = normalize_dir(dest_dir)

    if kind == "auth":
        auth_ent = pascal(entity_name or "User")
        env_tbl = (
            os.getenv("AUTH_TABLE_NAME")
            or os.getenv("SVC_INFRA_AUTH_TABLE")
            or os.getenv("APF_AUTH_TABLE_NAME")
        )
        auth_tbl = (table_name or env_tbl or plural_snake(auth_ent)).strip()

        txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.auth",
            name="models.py.tmpl",
            subs={"AuthEntity": auth_ent, "auth_table_name": auth_tbl},
        )
    else:
        ent = pascal(entity_name)
        tbl = table_name or plural_snake(ent)

        tenant_model_field = (
            "    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)\n"
            if include_tenant
            else ""
        )
        soft_delete_model_field = (
            "    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n"
            "    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))\n"
            if include_soft_delete
            else "    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)\n"
        )
        tenant_arg = ', tenant_field="tenant_id"' if include_tenant else ""
        tenant_default = '"tenant_id"' if include_tenant else "None"
        txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.entity",
            name="models.py.tmpl",
            subs={
                "Entity": ent,
                "table_name": tbl,
                "tenant_field": tenant_model_field,
                "soft_delete_field": soft_delete_model_field,
                "tenant_arg": tenant_arg,
                "tenant_default": tenant_default,
            },
        )

    filename = models_filename or f"{snake(entity_name)}.py"
    res = write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}


def scaffold_schemas_core(
    *,
    dest_dir: Path | str,
    kind: Kind = "entity",
    entity_name: str = "Item",
    include_tenant: bool = True,
    overwrite: bool = False,
    schemas_filename: Optional[str] = None,  # <--- NEW
) -> Dict[str, Any]:
    """Create only a schema file (defaults to <snake(entity)>.py unless schemas_filename is provided)."""
    dest = normalize_dir(dest_dir)

    if kind == "auth":
        auth_ent = pascal(entity_name or "User")
        txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.auth",
            name="schemas.py.tmpl",
            subs={"AuthEntity": auth_ent},
        )
    else:
        ent = pascal(entity_name)
        tenant_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
        txt = render_template(
            tmpl_dir="svc_infra.db.sql.templates.models_schemas.entity",
            name="schemas.py.tmpl",
            subs={
                "Entity": ent,
                "tenant_field": tenant_field,
                "tenant_field_create": tenant_field,
                "tenant_field_update": tenant_field,
            },
        )

    filename = schemas_filename or f"{snake(entity_name)}.py"
    res = write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}
