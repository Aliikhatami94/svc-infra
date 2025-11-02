#!/usr/bin/env python
"""
Simple script to create database tables for the svc-infra-template example.

For demonstration purposes only. In production, use Alembic migrations.
"""
import asyncio
import sys
from pathlib import Path

from svc_infra_template.db import Base, get_engine
from svc_infra_template.db.models import Project, Task  # noqa: F401 - needed for metadata

# Add examples/src to path so we can import svc_infra_template
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def create_tables():
    """Create all tables defined in Base.metadata."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database tables created successfully!")
    print(f"   Tables: {', '.join(Base.metadata.tables.keys())}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
