import pytest
from sqlalchemy import text

from svc_infra.db import (
    get_database_url_from_env,
    is_async_url,
    build_engine,
    ensure_database_exists,
    init_alembic,
    revision,
)


# ---------- Env helpers ----------

def test_get_database_url_from_env_precedence_and_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_URL", raising=False)

    # No vars when not required -> None
    assert get_database_url_from_env(required=False) is None

    # Set fallback only
    monkeypatch.setenv("DB_URL", "sqlite:///fallback.db")
    assert get_database_url_from_env() == "sqlite:///fallback.db"

    # Set primary and fallback -> primary wins
    monkeypatch.setenv("DATABASE_URL", "sqlite:///primary.db")
    assert get_database_url_from_env() == "sqlite:///primary.db"

    # Required and missing -> raises
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_URL", raising=False)
    with pytest.raises(RuntimeError):
        get_database_url_from_env(required=True)


# ---------- URL helpers ----------

def test_is_async_url_detects_variants():
    assert is_async_url("sqlite+aiosqlite:///:memory:") is True
    assert is_async_url("postgresql+asyncpg://u:p@localhost/db") is True
    assert is_async_url("mysql+asyncmy://u:p@localhost/db") is True

    assert is_async_url("sqlite:///:memory:") is False
    assert is_async_url("postgresql://u:p@localhost/db") is False


# ---------- Engine build ----------

def test_build_engine_sync_sqlite_and_ping():
    url = "sqlite:///:memory:"
    eng = build_engine(url)
    # Simple connectivity check
    with eng.begin() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1
    eng.dispose()


# ---------- ensure_database_exists ----------

def test_ensure_database_exists_sqlite_creates_parent_dir(tmp_path):
    db_dir = tmp_path / "nested"
    db_path = db_dir / "app.db"
    url = f"sqlite:///{db_path}"

    assert not db_dir.exists()
    ensure_database_exists(url)
    assert db_dir.exists() and db_dir.is_dir()

    # Optional: actually open a connection to create the file
    eng = build_engine(url)
    with eng.begin() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1
    eng.dispose()


# ---------- Alembic scaffolding ----------

def test_init_alembic_sync_creates_files(tmp_path, monkeypatch):
    # Use sync sqlite for dialect detection in alembic.ini
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    project = tmp_path / "proj_sync"
    mig_dir = init_alembic(project, async_db=False)

    # Files/dirs exist
    assert mig_dir.exists() and mig_dir.is_dir()
    assert (project / "alembic.ini").exists()
    assert (mig_dir / "env.py").exists()
    assert (mig_dir / "versions").exists()

    # Check basic content markers
    ini_text = (project / "alembic.ini").read_text()
    assert "script_location = migrations" in ini_text
    assert "dialect_name = sqlite" in ini_text

    env_text = (mig_dir / "env.py").read_text()
    # Packages list injected (empty by default)
    assert "DISCOVER_PACKAGES: List[str] = []" in env_text
    assert "engine_from_config" in env_text  # sync template


def test_init_alembic_async_creates_files(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    project = tmp_path / "proj_async"
    mig_dir = init_alembic(project, async_db=True)

    assert mig_dir.exists() and (mig_dir / "env.py").exists()

    env_text = (mig_dir / "env.py").read_text()
    assert "create_async_engine" in env_text
    assert "_asyncio.run(run_migrations_online())" in env_text


# ---------- Alembic command helper (smoke) ----------

def test_alembic_revision_creates_version_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    project = tmp_path / "proj_rev"

    # Set up alembic structure
    mig_dir = init_alembic(project, async_db=False)
    versions = mig_dir / "versions"
    assert versions.exists() and versions.is_dir()

    # Run revision
    revision(project_root=project, message="init", autogenerate=False)

    created = list(versions.glob("*.py"))
    assert len(created) >= 1
    content = created[0].read_text()
    assert "revision =" in content

