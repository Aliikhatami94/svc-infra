from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Dict, Any, Optional, Literal

# ---------------- helpers ----------------

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

_INIT_CONTENT_PAIRED = 'from . import models, schemas\n\n__all__ = ["models", "schemas"]\n'
_INIT_CONTENT_MINIMAL = '# package marker; add explicit exports here if desired\n'

def _ensure_init_py(dir_path: Path, overwrite: bool, paired: bool) -> Dict[str, Any]:
    """Create __init__.py; paired=True writes models/schemas re-exports, otherwise minimal."""
    content = _INIT_CONTENT_PAIRED if paired else _INIT_CONTENT_MINIMAL
    return _write(dir_path / "__init__.py", content, overwrite)

# ---------------- auth templates (loaded from package) ----------------

def _render_auth_template(name: str) -> str:
    import importlib.resources as pkg
    from string import Template as _T
    txt = pkg.files("svc_infra.db.setup.templates.models_schemas.auth").joinpath(name).read_text(encoding="utf-8")
    return _T(txt).substitute({})  # no variables today

# ---------------- entity templates (loaded from package only) ----------------

def _render_entity_template(name: str, subs: Dict[str, Any]) -> str:
    """Render an entity template file using string.Template.

    Looks up templates under svc_infra.db.setup.templates.models_schemas.entity/<name> and requires them to exist.
    """
    import importlib.resources as pkg
    txt = pkg.files("svc_infra.db.setup.templates.models_schemas.entity").joinpath(name).read_text(encoding="utf-8")
    return Template(txt).substitute(subs)

# ---------------- tiny utilities ----------------

def _normalize_entity_name(name: str) -> str:
    parts = [p for p in _snake(name).split("_") if p]
    return "".join(p.capitalize() for p in parts) or "Item"

def _snake(name: str) -> str:
    import re
    # Insert underscores at CamelCase boundaries, then normalize
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")

def _suggest_table_name(entity_pascal: str) -> str:
    base = _snake(entity_pascal)
    return base + "s" if not base.endswith("s") else base

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
        models_filename: Optional[str] = None,   # <--- NEW
        schemas_filename: Optional[str] = None,  # <--- NEW
) -> Dict[str, Any]:
    """
    Create starter model + schema files.

    Filenames:
      - same_dir=True  -> models.py + schemas.py (paired).
      - same_dir=False -> defaults to <snake(entity)>.py in each dir, unless you pass
                          --models-filename / --schemas-filename.
    """
    models_dir = _normalize_dir(models_dir)
    schemas_dir = _normalize_dir(models_dir if same_dir else schemas_dir)

    # content per kind
    if kind == "auth":
        models_txt = _render_auth_template("models.py.tmpl")
        schemas_txt = _render_auth_template("schemas.py.tmpl")
    else:
        ent = _normalize_entity_name(entity_name)
        tbl = table_name or _suggest_table_name(ent)
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
        constraints = (
            '    __table_args__ = (\n'
            f'        UniqueConstraint("tenant_id", "name", name="uq_{tbl}_tenant_name"),\n'
            '    )\n'
        ) if include_tenant else ""
        indexes = f'Index("ix_{tbl}_tenant_id", {ent}.tenant_id)\n' if include_tenant else ""

        models_txt = _render_entity_template(
            "models.py.tmpl",
            subs={
                "Entity": ent,
                "table_name": tbl,
                "tenant_field": tenant_model_field,
                "soft_delete_field": soft_delete_model_field,
                "constraints": constraints,
                "indexes": indexes,
            },
        )

        tenant_schema_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
        schemas_txt = _render_entity_template(
            "schemas.py.tmpl",
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
        default_stub = _snake(entity_name)
        models_name = models_filename or f"{default_stub}.py"
        schemas_name = schemas_filename or f"{default_stub}.py"
        models_path = models_dir / models_name
        schemas_path = schemas_dir / schemas_name

    # write
    models_res = _write(models_path, models_txt, overwrite)
    schemas_res = _write(schemas_path, schemas_txt, overwrite)

    # __init__ files
    init_results = []
    init_results.append(_ensure_init_py(models_dir, overwrite, paired=same_dir))
    if schemas_dir != models_dir:
        init_results.append(_ensure_init_py(schemas_dir, overwrite, paired=False))

    return {"status": "ok", "results": {"models": models_res, "schemas": schemas_res, "inits": init_results}}

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
    dest = _normalize_dir(dest_dir)

    if kind == "auth":
        txt = _render_auth_template("models.py.tmpl")
    else:
        ent = _normalize_entity_name(entity_name)
        tbl = table_name or _suggest_table_name(ent)
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
        constraints = (
            '    __table_args__ = (\n'
            f'        UniqueConstraint("tenant_id", "name", name="uq_{tbl}_tenant_name"),\n'
            '    )\n'
        ) if include_tenant else ""
        indexes = f'Index("ix_{tbl}_tenant_id", {ent}.tenant_id)\n' if include_tenant else ""
        txt = _render_entity_template(
            "models.py.tmpl",
            subs={
                "Entity": ent,
                "table_name": tbl,
                "tenant_field": tenant_model_field,
                "soft_delete_field": soft_delete_model_field,
                "constraints": constraints,
                "indexes": indexes,
            },
        )

    filename = models_filename or f"{_snake(entity_name)}.py"
    res = _write(dest / filename, txt, overwrite)
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
    dest = _normalize_dir(dest_dir)

    if kind == "auth":
        txt = _render_auth_template("schemas.py.tmpl")
    else:
        ent = _normalize_entity_name(entity_name)
        tenant_field = "    tenant_id: Optional[str] = None\n" if include_tenant else ""
        txt = _render_entity_template(
            "schemas.py.tmpl",
            subs={
                "Entity": ent,
                "tenant_field": tenant_field,
                "tenant_field_create": tenant_field,
                "tenant_field_update": tenant_field,
            },
        )

    filename = schemas_filename or f"{_snake(entity_name)}.py"
    res = _write(dest / filename, txt, overwrite)
    _ensure_init_py(dest, overwrite, paired=False)
    return {"status": "ok", "result": res}