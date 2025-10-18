from __future__ import annotations

import json
import logging
from types import SimpleNamespace

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
    vals = _env_name_list_to_enum_values(["prod", "Production", "DEV", "staging", "local"])
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
    setup_logging(level=LogLevelOptions.INFO, fmt="json", filter_envs=["local"])  # default env

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
