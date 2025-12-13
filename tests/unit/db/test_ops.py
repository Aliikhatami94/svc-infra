"""Unit tests for svc_infra.db.ops module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestNormalizeDatabaseUrl:
    """Tests for URL normalization."""

    def test_postgres_to_postgresql(self):
        """Should convert postgres:// to postgresql://."""
        from svc_infra.db.sql.utils import _normalize_database_url

        url = "postgres://user:pass@host:5432/db"
        assert _normalize_database_url(url) == "postgresql://user:pass@host:5432/db"

    def test_postgresql_unchanged(self):
        """Should not modify postgresql:// URLs."""
        from svc_infra.db.sql.utils import _normalize_database_url

        url = "postgresql://user:pass@host:5432/db"
        assert _normalize_database_url(url) == url

    def test_asyncpg_unchanged(self):
        """Should not modify postgresql+asyncpg:// URLs."""
        from svc_infra.db.sql.utils import _normalize_database_url

        url = "postgresql+asyncpg://user:pass@host:5432/db"
        assert _normalize_database_url(url) == url

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        from svc_infra.db.sql.utils import _normalize_database_url

        url = "  postgres://user:pass@host:5432/db  \n"
        assert _normalize_database_url(url) == "postgresql://user:pass@host:5432/db"


class TestGetDatabaseUrlFromEnv:
    """Tests for get_database_url_from_env with new Railway variables."""

    def test_database_url_is_checked(self, monkeypatch):
        """Should check DATABASE_URL environment variable."""
        from svc_infra.db.sql.utils import get_database_url_from_env

        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.delenv("DB_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgres://test:test@localhost/testdb")

        url = get_database_url_from_env(required=True)
        # Should be normalized to postgresql://
        assert url == "postgresql://test:test@localhost/testdb"

    def test_database_url_private_is_checked(self, monkeypatch):
        """Should check DATABASE_URL_PRIVATE (Railway private networking)."""
        from svc_infra.db.sql.utils import get_database_url_from_env

        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.delenv("DB_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL_PRIVATE", "postgres://user:pass@private.railway/db")

        url = get_database_url_from_env(required=True)
        assert url == "postgresql://user:pass@private.railway/db"

    def test_sql_url_takes_precedence(self, monkeypatch):
        """SQL_URL should take precedence over DATABASE_URL."""
        from svc_infra.db.sql.utils import get_database_url_from_env

        monkeypatch.setenv("SQL_URL", "postgresql://primary@host/db")
        monkeypatch.setenv("DATABASE_URL", "postgresql://secondary@host/db")

        url = get_database_url_from_env(required=True)
        assert url == "postgresql://primary@host/db"

    def test_normalize_can_be_disabled(self, monkeypatch):
        """Should be able to disable URL normalization."""
        from svc_infra.db.sql.utils import get_database_url_from_env

        monkeypatch.setenv("SQL_URL", "postgres://user:pass@host/db")

        url = get_database_url_from_env(required=True, normalize=False)
        assert url == "postgres://user:pass@host/db"


class TestDefaultDbEnvVars:
    """Tests for DEFAULT_DB_ENV_VARS constant."""

    def test_includes_railway_variables(self):
        """Should include Railway environment variable names."""
        from svc_infra.db.sql.constants import DEFAULT_DB_ENV_VARS

        assert "DATABASE_URL" in DEFAULT_DB_ENV_VARS
        assert "DATABASE_URL_PRIVATE" in DEFAULT_DB_ENV_VARS

    def test_sql_url_is_first(self):
        """SQL_URL should be checked first (highest priority)."""
        from svc_infra.db.sql.constants import DEFAULT_DB_ENV_VARS

        assert DEFAULT_DB_ENV_VARS[0] == "SQL_URL"


class TestWaitForDatabase:
    """Tests for wait_for_database function."""

    def test_returns_true_when_db_ready(self):
        """Should return True when database is immediately available."""
        from svc_infra.db.ops import wait_for_database

        mock_conn = MagicMock()
        with patch("svc_infra.db.ops._get_connection", return_value=mock_conn):
            result = wait_for_database(url="postgresql://test/db", timeout=5, verbose=False)

        assert result is True
        mock_conn.close.assert_called_once()

    def test_returns_false_on_timeout(self):
        """Should return False when timeout is reached."""
        from svc_infra.db.ops import wait_for_database

        with patch("svc_infra.db.ops._get_connection", side_effect=Exception("Connection refused")):
            result = wait_for_database(
                url="postgresql://test/db",
                timeout=0.5,
                interval=0.1,
                verbose=False,
            )

        assert result is False

    def test_retries_on_failure(self):
        """Should retry connection on initial failures."""
        from svc_infra.db.ops import wait_for_database

        mock_conn = MagicMock()
        call_count = 0

        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Not ready yet")
            return mock_conn

        with patch("svc_infra.db.ops._get_connection", side_effect=failing_then_success):
            result = wait_for_database(
                url="postgresql://test/db",
                timeout=5,
                interval=0.1,
                verbose=False,
            )

        assert result is True
        assert call_count == 3


class TestRunSyncSql:
    """Tests for run_sync_sql function."""

    def test_executes_sql(self):
        """Should execute SQL statement."""
        from svc_infra.db.ops import run_sync_sql

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("svc_infra.db.ops._get_connection", return_value=mock_conn):
            run_sync_sql("SELECT 1", url="postgresql://test/db")

        # Should set statement timeout and execute
        assert mock_cursor.execute.call_count == 2  # timeout + actual query
        mock_conn.commit.assert_called_once()

    def test_fetch_returns_rows(self):
        """Should return rows when fetch=True."""
        from svc_infra.db.ops import run_sync_sql

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "a"), (2, "b")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("svc_infra.db.ops._get_connection", return_value=mock_conn):
            result = run_sync_sql("SELECT * FROM test", url="postgresql://test/db", fetch=True)

        assert result == [(1, "a"), (2, "b")]

    def test_params_are_passed(self):
        """Should pass parameters for parameterized queries."""
        from svc_infra.db.ops import run_sync_sql

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("svc_infra.db.ops._get_connection", return_value=mock_conn):
            run_sync_sql(
                "SELECT * FROM users WHERE id = %s", params=(42,), url="postgresql://test/db"
            )

        # Second call should be with params
        calls = mock_cursor.execute.call_args_list
        assert calls[1] == (("SELECT * FROM users WHERE id = %s", (42,)),)


class TestDropTableSafe:
    """Tests for drop_table_safe function."""

    def test_drops_table(self):
        """Should drop table successfully."""
        from svc_infra.db.ops import drop_table_safe

        with patch("svc_infra.db.ops.kill_blocking_queries", return_value=[]):
            with patch("svc_infra.db.ops.run_sync_sql") as mock_run:
                result = drop_table_safe("test_table", url="postgresql://test/db")

        assert result is True
        mock_run.assert_called_once()
        assert "DROP TABLE" in mock_run.call_args[0][0]
        assert "test_table" in mock_run.call_args[0][0]

    def test_if_exists_in_sql(self):
        """Should include IF EXISTS by default."""
        from svc_infra.db.ops import drop_table_safe

        with patch("svc_infra.db.ops.kill_blocking_queries", return_value=[]):
            with patch("svc_infra.db.ops.run_sync_sql") as mock_run:
                drop_table_safe("test_table", url="postgresql://test/db")

        sql = mock_run.call_args[0][0]
        assert "IF EXISTS" in sql

    def test_cascade_option(self):
        """Should include CASCADE when requested."""
        from svc_infra.db.ops import drop_table_safe

        with patch("svc_infra.db.ops.kill_blocking_queries", return_value=[]):
            with patch("svc_infra.db.ops.run_sync_sql") as mock_run:
                drop_table_safe("test_table", url="postgresql://test/db", cascade=True)

        sql = mock_run.call_args[0][0]
        assert "CASCADE" in sql

    def test_returns_false_on_error(self):
        """Should return False on error."""
        from svc_infra.db.ops import drop_table_safe

        with patch("svc_infra.db.ops.kill_blocking_queries", return_value=[]):
            with patch("svc_infra.db.ops.run_sync_sql", side_effect=Exception("Lock timeout")):
                result = drop_table_safe("test_table", url="postgresql://test/db")

        assert result is False


class TestGetDatabaseUrl:
    """Tests for get_database_url convenience function."""

    def test_wraps_get_database_url_from_env(self, monkeypatch):
        """Should call get_database_url_from_env with correct params."""
        from svc_infra.db.ops import get_database_url

        monkeypatch.setenv("SQL_URL", "postgresql://test/db")

        url = get_database_url()
        assert url == "postgresql://test/db"

    def test_normalizes_by_default(self, monkeypatch):
        """Should normalize URLs by default."""
        from svc_infra.db.ops import get_database_url

        monkeypatch.setenv("SQL_URL", "postgres://test/db")

        url = get_database_url()
        assert url == "postgresql://test/db"
