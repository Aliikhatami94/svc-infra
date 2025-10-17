"""
Compatibility shim so `tests.db.sql.test_sql_seed_cli:my_seed` import path remains valid
and updates state in the unit module for assertions.
"""

import sys

from tests.unit.db.sql import test_sql_seed_cli as _unit  # noqa: F401

# Expose the same global used by the unit test
called = _unit.called


def my_seed():  # noqa: D401, ANN201
    # Call the unit version
    _unit.my_seed()
    # Also ensure the unit module seen by pytest has its state updated
    mod = sys.modules.get("tests.unit.db.sql.test_sql_seed_cli")
    if mod is not None and hasattr(mod, "called"):
        try:
            mod.called["seed"] += 0  # touch to ensure same object
        except Exception:
            pass
    return None


__all__ = ["my_seed", "called"]
