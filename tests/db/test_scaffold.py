from pathlib import Path

from svc_infra.db.manage.scaffold import (
    scaffold_core,
    scaffold_models_core,
    scaffold_schemas_core,
)


def read(p: Path) -> str:
    return Path(p).read_text(encoding="utf-8")


# ---------- scafold_core (same_dir) ----------

def test_scaffold_core_same_dir_creates_paired_files_and_init(tmp_path: Path):
    pkg = tmp_path / "pkg"

    res = scaffold_core(
        models_dir=pkg,
        schemas_dir=pkg,  # ignored when same_dir=True
        same_dir=True,
        entity_name="WidgetThing",
        include_tenant=True,
        overwrite=False,
    )

    # Files exist
    models_path = pkg / "models.py"
    schemas_path = pkg / "schemas.py"
    init_path = pkg / "__init__.py"

    assert models_path.exists() and schemas_path.exists() and init_path.exists()

    # __init__ should be paired exports
    init_txt = read(init_path)
    assert "from . import models, schemas" in init_txt
    assert "__all__ = [\"models\", \"schemas\"]" in init_txt

    # Content sanity checks
    m = read(models_path)
    s = read(schemas_path)

    # Entity normalization -> PascalCase
    assert "class WidgetThing(" in m
    # Default table name: snake(entity) + 's'
    assert '__tablename__ = "widget_things"' in m

    # Tenant bits are present in models and schemas
    assert "tenant_id:" in m
    assert 'UniqueConstraint("tenant_id", "name", name="uq_widget_things_tenant_name")' in m
    assert 'Index("ix_widget_things_tenant_id"' in m
    assert "tenant_id:" in s

    # Pydantic schema classes exist
    assert "class WidgetThingRead(WidgetThingBase, Timestamped):" in s
    assert "class WidgetThingCreate(BaseModel):" in s
    assert "class WidgetThingUpdate(BaseModel):" in s


# ---------- scaffold_core (separate dirs + custom filenames) ----------

def test_scaffold_core_separate_dirs_custom_filenames_no_tenant(tmp_path: Path):
    models_dir = tmp_path / "models"
    schemas_dir = tmp_path / "schemas"

    res = scaffold_core(
        models_dir=models_dir,
        schemas_dir=schemas_dir,
        same_dir=False,
        entity_name="Gizmo",
        include_tenant=False,
        overwrite=False,
        models_filename="m_gizmo.py",
        schemas_filename="s_gizmo.py",
    )

    m_path = models_dir / "m_gizmo.py"
    s_path = schemas_dir / "s_gizmo.py"

    assert m_path.exists() and s_path.exists()

    # __init__.py should be minimal markers in both dirs
    m_init = read(models_dir / "__init__.py")
    s_init = read(schemas_dir / "__init__.py")
    assert m_init.startswith("# package marker")
    assert s_init.startswith("# package marker")

    m = read(m_path)
    s = read(s_path)

    # No tenant-specific content
    assert "tenant_id" not in m
    assert "UniqueConstraint(" not in m
    assert "Index(" not in m
    assert "tenant_id" not in s

    # Table name pluralization
    assert '__tablename__ = "gizmos"' in m


# ---------- scaffold_models_core / scaffold_schemas_core (overwrite + toggles) ----------

def test_scaffold_models_core_overwrite_and_soft_delete_toggle(tmp_path: Path):
    dest = tmp_path / "models_only"

    # First write with soft delete ON
    r1 = scaffold_models_core(dest_dir=dest, entity_name="FooBar", include_soft_delete=True)
    assert r1["status"] == "ok" and r1["result"]["action"] == "wrote"

    file_path = dest / "foo_bar.py"  # default snake filename
    txt1 = read(file_path)
    assert "deleted_at:" in txt1  # soft delete present

    # Second write without overwrite -> should skip and keep original content
    r2 = scaffold_models_core(dest_dir=dest, entity_name="FooBar", include_soft_delete=False, overwrite=False)
    assert r2["result"]["action"] == "skipped"
    assert read(file_path) == txt1

    # Overwrite True -> should rewrite without deleted_at
    r3 = scaffold_models_core(dest_dir=dest, entity_name="FooBar", include_soft_delete=False, overwrite=True)
    assert r3["result"]["action"] == "wrote"
    txt3 = read(file_path)
    assert "deleted_at:" not in txt3
    assert "is_active:" in txt3

    # __init__.py minimal exists
    init_txt = read(dest / "__init__.py")
    assert init_txt.startswith("# package marker")


def test_scaffold_schemas_core_overwrite_and_tenant_toggle(tmp_path: Path):
    dest = tmp_path / "schemas_only"

    # First write with tenant ON
    r1 = scaffold_schemas_core(dest_dir=dest, entity_name="FooBar", include_tenant=True)
    assert r1["status"] == "ok" and r1["result"]["action"] == "wrote"

    file_path = dest / "foo_bar.py"
    txt1 = read(file_path)
    assert "tenant_id:" in txt1

    # Second write without overwrite -> should skip
    r2 = scaffold_schemas_core(dest_dir=dest, entity_name="FooBar", include_tenant=False, overwrite=False)
    assert r2["result"]["action"] == "skipped"
    assert read(file_path) == txt1

    # Overwrite True -> tenant removed
    r3 = scaffold_schemas_core(dest_dir=dest, entity_name="FooBar", include_tenant=False, overwrite=True)
    assert r3["result"]["action"] == "wrote"
    txt3 = read(file_path)
    assert "tenant_id:" not in txt3

    # __init__.py minimal exists
    init_txt = read(dest / "__init__.py")
    assert init_txt.startswith("# package marker")

