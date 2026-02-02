"""Async database engine and session management for Postgres."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str | None:
    """Get the database URL from environment variable."""
    return os.getenv("DATABASE_URL")


async def init_database() -> None:
    """Initialize the database engine and session factory."""
    global _engine, _session_factory

    url = get_database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required for database-backed storage"
        )

    _engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_database() -> None:
    """Close the database engine."""
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine | None:
    """Get the database engine (None if database is not enabled)."""
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)

    Raises:
        RuntimeError: If database is not initialized
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
