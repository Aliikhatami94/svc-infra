"""Unit tests for svc_infra.logging module."""

from __future__ import annotations

import io
import json
import logging
import os
import sys
from unittest.mock import patch


class TestFlush:
    """Tests for flush() function."""

    def test_flushes_stdout_and_stderr(self):
        """Should flush both stdout and stderr."""
        from svc_infra.logging import flush

        # Create mock streams
        mock_stdout = io.StringIO()
        mock_stderr = io.StringIO()

        with patch.object(sys, "stdout", mock_stdout):
            with patch.object(sys, "stderr", mock_stderr):
                # Write something
                sys.stdout.write("test stdout")
                sys.stderr.write("test stderr")

                # Flush should not raise
                flush()

    def test_flush_is_safe_to_call_multiple_times(self):
        """Should be safe to call multiple times."""
        from svc_infra.logging import flush

        # Should not raise
        flush()
        flush()
        flush()


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_formats_as_json(self):
        """Should format log records as JSON."""
        from svc_infra.logging import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self):
        """Should include extra fields in JSON output."""
        from svc_infra.logging import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.user_id = 123
        record.request_id = "abc-123"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["user_id"] == 123
        assert parsed["request_id"] == "abc-123"

    def test_includes_exception_info(self):
        """Should include exception info when present."""
        from svc_infra.logging import JsonFormatter

        formatter = JsonFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test error" in parsed["exception"]


class TestTextFormatter:
    """Tests for TextFormatter class."""

    def test_formats_as_text(self):
        """Should format log records as human-readable text."""
        from svc_infra.logging import TextFormatter

        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "[INFO]" in output
        assert "test.logger" in output
        assert "Test message" in output


class TestConfigureForContainer:
    """Tests for configure_for_container() function."""

    def test_sets_unbuffered_env(self):
        """Should set PYTHONUNBUFFERED environment variable."""
        from svc_infra.logging import configure_for_container

        # Clear any existing value
        os.environ.pop("PYTHONUNBUFFERED", None)

        configure_for_container()

        assert os.environ.get("PYTHONUNBUFFERED") == "1"

    def test_configures_root_logger(self):
        """Should configure the root logger."""
        from svc_infra.logging import configure_for_container

        configure_for_container(level="DEBUG")

        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) > 0

    def test_uses_json_formatter_by_default(self):
        """Should use JSON formatter by default."""
        from svc_infra.logging import JsonFormatter, configure_for_container

        # Ensure LOG_FORMAT is not "text"
        os.environ.pop("LOG_FORMAT", None)

        configure_for_container()

        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_uses_text_formatter_when_requested(self):
        """Should use text formatter when json_format=False."""
        from svc_infra.logging import TextFormatter, configure_for_container

        configure_for_container(json_format=False)

        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, TextFormatter)

    def test_respects_log_format_env(self, monkeypatch):
        """Should respect LOG_FORMAT environment variable."""
        monkeypatch.setenv("LOG_FORMAT", "text")

        # Need to reimport to pick up env var
        import importlib

        import svc_infra.logging

        importlib.reload(svc_infra.logging)
        svc_infra.logging.configure_for_container()

        root = logging.getLogger()
        handler = root.handlers[0]
        # Check class name since identity changes after reload
        assert handler.formatter.__class__.__name__ == "TextFormatter"

        # Reset
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        importlib.reload(svc_infra.logging)


class TestGetLogger:
    """Tests for get_logger() function."""

    def test_returns_logger(self):
        """Should return a logger instance."""
        from svc_infra.logging import get_logger

        logger = get_logger("test.module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_same_name_returns_same_logger(self):
        """Should return the same logger for the same name."""
        from svc_infra.logging import get_logger

        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")

        assert logger1 is logger2


class TestWithContext:
    """Tests for with_context() context manager."""

    def test_adds_context_within_block(self):
        """Should add context within the context manager block."""
        from svc_infra.logging import get_context, with_context

        with with_context(request_id="abc-123", user_id=42):
            ctx = get_context()
            assert ctx["request_id"] == "abc-123"
            assert ctx["user_id"] == 42

    def test_clears_context_after_block(self):
        """Should clear context after exiting the block."""
        from svc_infra.logging import clear_context, get_context, with_context

        clear_context()  # Start clean

        with with_context(request_id="abc-123"):
            pass

        ctx = get_context()
        assert "request_id" not in ctx

    def test_nested_contexts(self):
        """Should support nested contexts."""
        from svc_infra.logging import clear_context, get_context, with_context

        clear_context()

        with with_context(outer="value1"):
            with with_context(inner="value2"):
                ctx = get_context()
                assert ctx["outer"] == "value1"
                assert ctx["inner"] == "value2"

            # Inner context should be cleared
            ctx = get_context()
            assert ctx["outer"] == "value1"
            assert "inner" not in ctx

    def test_restores_previous_context(self):
        """Should restore previous context after nested block."""
        from svc_infra.logging import clear_context, get_context, with_context

        clear_context()

        with with_context(key="original"):
            with with_context(key="overridden"):
                assert get_context()["key"] == "overridden"

            # Should be restored
            assert get_context()["key"] == "original"


class TestSetAndClearContext:
    """Tests for set_context() and clear_context() functions."""

    def test_set_context_adds_values(self):
        """Should add values to context."""
        from svc_infra.logging import clear_context, get_context, set_context

        clear_context()

        set_context(tenant_id="tenant-1")
        assert get_context()["tenant_id"] == "tenant-1"

        set_context(user_id=123)
        ctx = get_context()
        assert ctx["tenant_id"] == "tenant-1"
        assert ctx["user_id"] == 123

    def test_clear_context_removes_all(self):
        """Should remove all context values."""
        from svc_infra.logging import clear_context, get_context, set_context

        set_context(a=1, b=2, c=3)
        clear_context()

        assert get_context() == {}

    def test_get_context_returns_copy(self):
        """Should return a copy, not the original dict."""
        from svc_infra.logging import clear_context, get_context, set_context

        clear_context()
        set_context(key="value")

        ctx = get_context()
        ctx["modified"] = True

        # Original should not be modified
        assert "modified" not in get_context()


class TestContextInJsonOutput:
    """Tests for context appearing in JSON log output."""

    def test_context_appears_in_json_logs(self):
        """Context should appear in JSON formatted log output."""
        from svc_infra.logging import JsonFormatter, clear_context, set_context

        clear_context()
        set_context(request_id="test-123", tenant_id="tenant-abc")

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["request_id"] == "test-123"
        assert parsed["tenant_id"] == "tenant-abc"

        clear_context()
