"""SQLAlchemy 2.0 async engine and session factory.

Provides the async engine (asyncpg driver), an async session factory,
a get_session async context manager for dependency injection, and a
dispose_engine helper for clean shutdown.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


@lru_cache(maxsize=1)
def _get_settings() -> Settings:
    return Settings()


def _make_url(database_url: str) -> str:
    """Convert postgres:// to postgresql+asyncpg:// if needed."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call."""
    url = _make_url(_get_settings().DATABASE_URL)
    return create_async_engine(url, echo=False, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared async session factory."""
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, rolling back on error."""
    session = get_async_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the async engine for clean shutdown."""
    await get_engine().dispose()
