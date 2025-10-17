# Compatibility shim to ensure `from tests.db.sql.conftest` continues to work
from tests.unit.db.sql.conftest import *  # noqa: F401,F403
