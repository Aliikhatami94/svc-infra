from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    """Automatically mark security-related tests so `-m security` selects them.

    We tag tests under `tests/security/` and `tests/auth/` with the `security` marker.
    """
    for item in items:
        path = str(item.fspath)
        # Normalize separators just in case
        norm = path.replace("\\", "/")
        if "/tests/security/" in norm or "/tests/auth/" in norm:
            item.add_marker(pytest.mark.security)
        # Include API tests that assert rate limiting / request-size or metrics hooks
        if "/tests/api/" in norm and (
            "rate_limit" in norm or "request_size" in norm or "metrics_hooks" in norm
        ):
            item.add_marker(pytest.mark.security)
            # Also mark as ratelimit when appropriate
            if "rate_limit" in norm or "metrics_hooks" in norm:
                item.add_marker(pytest.mark.ratelimit)
        # Directly mark ratelimit tests anywhere in the path containing 'rate_limit'
        if "rate_limit" in norm:
            item.add_marker(pytest.mark.ratelimit)

        # Mark tenancy-related tests (either under a tenancy folder or filename contains 'tenant')
        if "/tests/tenancy/" in norm or "tenant" in norm:
            item.add_marker(pytest.mark.tenancy)


def pytest_configure(config):
    # Ensure custom markers are registered even if pyproject.toml isn't picked up in some contexts
    for name, desc in [
        ("security", "Security and auth hardening tests"),
        ("ratelimit", "Rate limiting and abuse protection tests"),
        ("concurrency", "Idempotency and concurrency control tests"),
        ("jobs", "Background jobs and scheduling tests"),
        ("webhooks", "Webhooks framework tests"),
        ("tenancy", "Tenancy isolation and enforcement tests"),
        ("data_lifecycle", "Data lifecycle (fixtures, retention, erasure, backups)"),
        ("ops", "SLOs & Ops tests (probes, breaker, instrumentation)"),
        ("dx", "Developer experience and quality gates tests"),
    ]:
        config.addinivalue_line("markers", f"{name}: {desc}")
