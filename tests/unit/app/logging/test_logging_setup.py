from __future__ import annotations

import json
import logging

import pytest

from svc_infra.app.logging import LogLevelOptions, setup_logging
from svc_infra.app.logging.filter import _is_metrics_like
from svc_infra.app.logging.formats import (
    JsonFormatter,
    _env_name_list_to_enum_values,
    _parse_paths_csv,
)


def test_json_formatter_includes_optional_fields():
    fmt = JsonFormatter()
    logger = logging.getLogger("test.json")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    logger.handlers[:] = [handler]

    class _Buffer:
        def __init__(self):
            self.data = ""

        def write(self, s):
            self.data += s

        def flush(self):
            pass

    buf = _Buffer()
    handler.stream = buf

    extra = {
        "request_id": "req-1",
        "http_method": "GET",
        "path": "/ping",
        "status_code": 200,
        "client_ip": "127.0.0.1",
        "user_agent": "pytest",
        "trace_id": "t-1",
        "span_id": "s-1",
    }
    logger.info("hello", extra=extra)

    payload = json.loads(buf.data)
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-1"
    assert payload["trace_id"] == "t-1"
    assert payload["span_id"] == "s-1"
    assert payload["http"] == {
        "method": "GET",
        "path": "/ping",
        "status": 200,
        "client_ip": "127.0.0.1",
        "user_agent": "pytest",
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("/metrics", ["/metrics"]),
        ("metrics", ["/metrics"]),
        ("/a,/b /c", ["/a", "/b", "/c"]),
    ],
)
def test_parse_paths_csv(raw, expected):
    assert _parse_paths_csv(raw) == expected


def test_env_name_list_to_enum_values_normalizes():
    vals = _env_name_list_to_enum_values(
        ["prod", "Production", "DEV", "staging", "local"]
    )
    assert vals == {"prod", "dev", "test", "local"}


def test_is_metrics_like_detects_request_line_dict_record():
    rec = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="",
        args=({"request_line": "GET /metrics HTTP/1.1"},),
        exc_info=None,
    )
    assert _is_metrics_like(rec, paths=["/metrics"]) is True


def test_is_metrics_like_detects_message_substring():
    rec = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /health HTTP/1.1" 200 OK',
        args=(),
        exc_info=None,
    )
    assert _is_metrics_like(rec, paths=["/metrics", "/health"]) is True


def test_setup_logging_applies_format_and_filters(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_DROP_PATHS", "/metrics, /health")

    # Ensure filter is enabled for the current test environment
    setup_logging(
        level=LogLevelOptions.INFO, fmt="json", filter_envs=["local"]
    )  # default env

    # Root logger configured
    root = logging.getLogger()
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)

    # Access logger has filter installed
    acc = logging.getLogger("uvicorn.access")
    msg = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /metrics HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    allowed = all(f.filter(msg) for f in acc.filters)
    assert allowed is False  # dropped due to filter


def _root_has_plain_formatter() -> bool:
    root = logging.getLogger()
    return any(
        isinstance(h.formatter, logging.Formatter)
        and not isinstance(h.formatter, JsonFormatter)
        for h in root.handlers
    )


def _root_has_json_formatter() -> bool:
    root = logging.getLogger()
    return any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)


def test_plain_formatter_when_fmt_plain(monkeypatch):
    # Ensure env does not force format
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    setup_logging(level=LogLevelOptions.INFO, fmt="plain", filter_envs=["local"])
    assert _root_has_plain_formatter() is True
    assert _root_has_json_formatter() is False


def test_auto_format_defaults_plain_in_nonprod(monkeypatch):
    # Force non-prod default
    import svc_infra.app.logging.formats as formats

    monkeypatch.setattr(formats, "IS_PROD", False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    setup_logging(level=LogLevelOptions.INFO, fmt=None, filter_envs=["local"])
    assert _root_has_plain_formatter() is True
    assert _root_has_json_formatter() is False


def test_auto_format_defaults_json_in_prod(monkeypatch):
    # Force prod default
    import svc_infra.app.logging.formats as formats

    monkeypatch.setattr(formats, "IS_PROD", True)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    setup_logging(level=LogLevelOptions.INFO, fmt=None, filter_envs=["local"])
    assert _root_has_json_formatter() is True


def test_drop_paths_argument_overrides_env(monkeypatch):
    # Remove any existing access filters from previous setup_logging calls
    for name in ("uvicorn.access", "gunicorn.access"):
        logger = logging.getLogger(name)
        logger.filters = []  # reset
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LOG_DROP_PATHS", "/metrics,/health")
    # drop_paths argument should take precedence
    setup_logging(
        level=LogLevelOptions.INFO,
        fmt="plain",
        filter_envs=["local"],
        drop_paths=["/only"],
    )

    acc = logging.getLogger("uvicorn.access")
    # This record matches env var but not the explicit drop list -> should be allowed
    rec_health = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /health HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    allowed_health = all(f.filter(rec_health) for f in acc.filters)
    assert allowed_health is True

    # This record matches the explicit drop list -> should be dropped
    rec_only = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /only HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    allowed_only = all(f.filter(rec_only) for f in acc.filters)
    assert allowed_only is False


def test_default_drops_metrics_when_enabled(monkeypatch):
    # Remove any existing access filters from previous setup_logging calls
    for name in ("uvicorn.access", "gunicorn.access"):
        logger = logging.getLogger(name)
        logger.filters = []  # reset
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("LOG_DROP_PATHS", raising=False)
    # No drop_paths provided -> defaults to ["/metrics"] when filter is enabled for env
    setup_logging(
        level=LogLevelOptions.INFO, fmt="plain", filter_envs=["local"]
    )  # enabled

    acc = logging.getLogger("uvicorn.access")
    rec_metrics = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /metrics HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    allowed = all(f.filter(rec_metrics) for f in acc.filters)
    assert allowed is False
