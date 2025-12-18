"""Database session and engine management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from svc_infra_template.settings import settings

# Global engine instance (created on first access)
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the database engine.

    Returns:
        AsyncEngine: SQLAlchemy async engine

    Raises:
        ValueError: If SQL_URL is not configured
    """
    global _engine

    if _engine is None:
        if not settings.sql_url:
            raise ValueError(
                "Database not configured. Set SQL_URL in .env file.\n"
                "Example: SQL_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname"
            )

        _engine = create_async_engine(
            settings.sql_url,
            pool_size=settings.sql_pool_size,
            max_overflow=settings.sql_max_overflow,
            pool_timeout=settings.sql_pool_timeout,
            echo=settings.app_env == "local",  # Log SQL in local env
        )

    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the session maker."""
    global _session_maker

    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI endpoints to get a database session.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
