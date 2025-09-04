from pathlib import Path

from svc_infra.db.scaffold import (
    scaffold_entity_core,
    scaffold_entity_models_core,
    scaffold_entity_schemas_core,
)


# Helpers ------------------------------------------------------------------

def read_text(p: Path) -> str:
    return Path(p).read_text(encoding="utf-8")


# Tests --------------------------------------------------------------------

def test_scaffold_models_defaults(tmp_path: Path):
    dest = tmp_path / "models"
    res = scaffold_entity_models_core(dest_dir=dest, entity_name="Project")

    # status/result contract
    assert res["status"] == "ok"
    out = res["result"]
    assert out["action"] == "wrote"

    # file was created with expected name
    model_path = dest / "project.py"
    assert model_path.exists()

    code = read_text(model_path)

    # core bits
    assert "class Project(" in code
    assert '__tablename__ = "projects"' in code  # pluralized suggestion
    assert "id: Mapped[uuid.UUID]" in code

    # tenant included by default
    assert "tenant_id: Mapped[Optional[str]]" in code
    assert "UniqueConstraint(\"tenant_id\", \"name\"" in code
    assert "Index(\"ix_projects_tenant_id\"" in code

    # soft delete disabled by default (no deleted_at), but is_active present
    assert "is_active: Mapped[bool]" in code
    assert "deleted_at: Mapped[Optional[datetime]]" not in code


def test_scaffold_models_with_soft_delete(tmp_path: Path):
    dest = tmp_path / "models"
    res = scaffold_entity_models_core(
        dest_dir=dest,
        entity_name="Note",
        include_soft_delete=True,
    )
    assert res["status"] == "ok"

    path = dest / "note.py"
    code = read_text(path)

    assert '__tablename__ = "notes"' in code
    assert "is_active: Mapped[bool]" in code
    assert "deleted_at: Mapped[Optional[datetime]]" in code


def test_scaffold_models_without_tenant(tmp_path: Path):
    dest = tmp_path / "models"
    res = scaffold_entity_models_core(
        dest_dir=dest,
        entity_name="Widget",
        include_tenant=False,
    )
    assert res["status"] == "ok"

    path = dest / "widget.py"
    code = read_text(path)

    # no tenant artifacts
    assert "tenant_id" not in code
    assert "UniqueConstraint(\"tenant_id\"" not in code
    assert "Index(\"ix_widgets_tenant_id\"" not in code


def test_scaffold_schemas_only(tmp_path: Path):
    dest = tmp_path / "schemas"
    res = scaffold_entity_schemas_core(dest_dir=dest, entity_name="Project")
    assert res["status"] == "ok"
    assert res["result"]["action"] == "wrote"

    path = dest / "project.py"
    code = read_text(path)

    assert "class ProjectBase" in code
    assert "class ProjectRead" in code
    assert "class ProjectCreate" in code
    assert "class ProjectUpdate" in code

    # default includes tenant in schemas
    assert "tenant_id: Optional[str]" in code


def test_scaffold_entity_core_writes_models_and_schemas_and_respects_overwrite(tmp_path: Path):
    models_dir = tmp_path / "m"
    schemas_dir = tmp_path / "s"

    # First write
    res1 = scaffold_entity_core(models_dir=models_dir, schemas_dir=schemas_dir, entity_name="Thing")
    assert res1["status"] == "ok"
    assert res1["results"]["models"]["action"] == "wrote"
    assert res1["results"]["schemas"]["action"] == "wrote"

    # Second write without overwrite should skip
    res2 = scaffold_entity_core(models_dir=models_dir, schemas_dir=schemas_dir, entity_name="Thing")
    assert res2["results"]["models"]["action"] == "skipped"
    assert res2["results"]["schemas"]["action"] == "skipped"

    # Third write with overwrite should write again
    res3 = scaffold_entity_core(
        models_dir=models_dir,
        schemas_dir=schemas_dir,
        entity_name="Thing",
        overwrite=True,
    )
    assert res3["results"]["models"]["action"] == "wrote"
    assert res3["results"]["schemas"]["action"] == "wrote"

    # Smoke: files exist with expected names
    assert (models_dir / "thing.py").exists()
    assert (schemas_dir / "thing.py").exists()

