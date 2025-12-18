"""Fixtures for CLI tests.

Disables Rich console styling to ensure consistent output across environments.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_rich_colors(monkeypatch):
    """Disable Rich colors/styling for consistent CLI output in CI.

    Rich terminal detection behaves differently in CI (no TTY) vs local,
    causing help text assertions to fail. Setting NO_COLOR ensures plain text output.
    """
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
