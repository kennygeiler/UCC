"""Alembic environment configuration with async support.

Uses the async engine from app.db and imports all models for autogenerate.
Reads DATABASE_URL from the process environment and from ``.env`` at the
repo root (same pattern as ``app.config``) so ``alembic`` works without
manually exporting variables.
"""

import asyncio
import sys
from pathlib import Path

from alembic import context
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

_REPO_ROOT = Path(__file__).resolve().parents[1]


class _AlembicDatabase(BaseSettings):
    """Minimal settings so migrations pick up ``DATABASE_URL`` from ``.env``."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str


try:
    database_url = _AlembicDatabase().DATABASE_URL.strip()
except ValidationError as exc:
    sys.exit(
        "Alembic requires DATABASE_URL. Add it to .env at the project root (copy from "
        ".env.example) or export it, e.g.:\n"
        "  export DATABASE_URL='postgresql+asyncpg://user:pass@localhost:5432/dbname'\n"
        f"Details: {exc}"
    )

if not database_url:
    sys.exit(
        "DATABASE_URL is empty. Set a non-empty connection string in .env or the environment."
    )

# Import all models so Alembic autogenerate detects them
from app.models.base import Base
from app.models import (  # noqa: F401
    UCCFiling,
    Lead,
    MCAlias,
    InternalDNC,
    DncReversalAudit,
    EnrichmentCache,
    ComplianceCheck,
    JobQueue,
    EnrichmentRetryQueue,
    StatePriority,
    ScraperRun,
    AgentHeartbeat,
    PipelineEvent,
    LanggraphCheckpoint,
)

config = context.config

# Normalize URL for asyncpg (may already be postgresql+asyncpg from .env)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode for SQL script generation."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations against a live connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — dispatches to async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
