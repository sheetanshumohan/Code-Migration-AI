"""
PostgreSQL Database Session & Engine Configuration
Async SQLAlchemy 2.0 implementation with connection pooling and async generators.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.db.postgres")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


# Initialize Async Engine with robust pooling settings
engine: AsyncEngine = create_async_engine(
    settings.POSTGRES_ASYNC_URI,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    """Dependency injection helper for FastAPI routes to yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database transaction rolled back due to error", error=str(e))
            raise
        finally:
            await session.close()


from contextlib import asynccontextmanager
from sqlalchemy.pool import NullPool


@asynccontextmanager
async def get_task_scoped_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated AsyncSession using NullPool strictly bound to the caller's active event loop."""
    task_engine = create_async_engine(
        settings.POSTGRES_ASYNC_URI,
        poolclass=NullPool,
        echo=False,
    )
    try:
        async with AsyncSession(task_engine) as session:
            yield session
    finally:
        await task_engine.dispose()


async def init_db_models() -> None:
    """Create tables on startup if not already created (useful for test/dev)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL database tables verified/initialized successfully")

