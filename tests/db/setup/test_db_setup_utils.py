from sqlalchemy import text, inspect
from alembic.config import Config

from svc_infra.db import utils
from svc_infra.db.utils import (
    with_database,
    _pg_quote_ident,
    _mysql_quote_ident,
    render_env_py,
    build_alembic_config,
    repair_alembic_state_if_needed,
    get_database_url_from_env,
)


def test_compose_url_from_parts_with_unix_socket(monkeypatch):
    # Ensure DATABASE_URL / DB_URL absent so composition is used
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_URL", raising=False)

    monkeypatch.setenv("DB_DIALECT", "postgresql")
    monkeypatch.setenv("DB_DRIVER", "psycopg")
    # Simulate a unix socket directory (private DNS/socket)
    monkeypatch.setenv("DB_HOST", "/cloudsql/instance")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_PARAMS", "sslmode=require&connect_timeout=5")

    url = get_database_url_from_env()
    assert url is not None
    # Should contain drivername and the unix socket encoded in query for pg
    assert "postgresql+psycopg" in url
    assert "host=/cloudsql/instance" in url or "host=%2Fcloudsql%2Finstance" in url
    assert "sslmode=require" in url


def test_with_database_replaces_database_name():
    url = "postgresql://u:p@localhost:5432/olddb"
    new = with_database(url, "newdb")
    assert new.database == "newdb"


def test_quote_identifiers_escape():
    assert _pg_quote_ident('weird"name') == 'weird""name'
    assert _mysql_quote_ident('bad`name') == 'bad``name'


def test_render_env_py_injects_packages_and_templates(tmp_path):
    # render both sync and async variants and ensure package list appears
    txt_sync = render_env_py(["pkg.a", "pkg.b"], async_db=False)
    assert "pkg.a" in txt_sync and "pkg.b" in txt_sync
    assert "engine_from_config" in txt_sync or "configure_mappers" in txt_sync

    txt_async = render_env_py(["pkg.x"], async_db=True)
    assert "pkg.x" in txt_async
    assert "create_async_engine" in txt_async


def test_build_alembic_config_uses_env_and_paths(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    # Write a dummy alembic.ini so build_alembic_config will load it if present
    ini = project / "alembic.ini"
    ini.write_text("[alembic]\n")

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    cfg = build_alembic_config(project, script_location="migrations")
    assert cfg.get_main_option("script_location")
    assert cfg.get_main_option("sqlalchemy.url") == "sqlite:///:memory:"
    assert cfg.get_main_option("prepend_sys_path") == str(project)


def test_repair_alembic_state_if_needed_drops_missing_revision(tmp_path):
    # Create a migrations/versions directory with a single local revision id
    project = tmp_path / "proj"
    versions = project / "migrations" / "versions"
    versions.mkdir(parents=True)

    local_rev = "local_rev_123"
    vf = versions / "0001_local.py"
    vf.write_text("revision = '" + local_rev + "'\n")

    # Create a sqlite database file and insert a different version into alembic_version
    db_path = tmp_path / "state.db"
    url = f"sqlite:///{db_path}"

    eng = utils.build_engine(url)
    try:
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": "remote_rev_999"})
    finally:
        eng.dispose()

    # Build alembic Config pointing to our migrations dir and DB
    cfg = Config()
    cfg.set_main_option("script_location", str((project / "migrations").resolve()))
    cfg.set_main_option("sqlalchemy.url", url)

    # Run repair - should drop the alembic_version table because remote_rev_999 isn't in local_ids
    repair_alembic_state_if_needed(cfg)

    eng2 = utils.build_engine(url)
    try:
        insp = inspect(eng2)
        assert not insp.has_table("alembic_version")
    finally:
        eng2.dispose()

