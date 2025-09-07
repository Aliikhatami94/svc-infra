from __future__ import annotations
import os
from typing import Optional

def apply_database_url(database_url: Optional[str]) -> None:
    """If provided, set DATABASE_URL for the current process."""
    if database_url:
        os.environ["DATABASE_URL"] = database_url