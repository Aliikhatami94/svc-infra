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
