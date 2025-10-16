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
