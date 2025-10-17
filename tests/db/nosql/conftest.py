# Compatibility shim to ensure `from tests.db.nosql.conftest` continues to work
from tests.unit.db.nosql.conftest import *  # noqa: F401,F403
