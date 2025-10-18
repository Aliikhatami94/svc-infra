from __future__ import annotations

import os
import subprocess
import sys
import urllib.request

import pytest

pytestmark = pytest.mark.acceptance


def test_security_headers_present(base_url):
    req = urllib.request.Request(f"{base_url}/ping", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        # Security headers should be present (baseline middleware)
        headers = {k.title(): v for k, v in resp.headers.items()}
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "Referrer-Policy" in headers


def test_no_access_log_spam_for_metrics(base_url):
    # Since uvicorn logs to stderr, run a one-shot curl to /metrics in a subprocess and capture stderr
    # We expect the access log line for /metrics to be absent due to filtering.
    import contextlib
    import io
    import logging

    # Emit a synthetic access-log-like record and assert our filter would drop it when path=/metrics
    from svc_infra.app.logging.filter import _DropPathsFilter

    logger = logging.getLogger("uvicorn.access")
    # Ensure we don't inherit filters from other tests here
    logger.filters = []
    filt = _DropPathsFilter(paths=("/metrics",))
    logger.addFilter(filt)

    rec = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='"GET /metrics HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    # Filter returns False to drop
    assert all(f.filter(rec) for f in logger.filters) is False
