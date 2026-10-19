# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — infrastructure
# LEGACY: source/dbConnection.php:1-8 (mysqli_connect lifecycle)
# COMPONENT: db/engine
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Async engine + session factory + FastAPI request dependency.

Lifetime:
  - `init_engine(settings)` builds the global AsyncEngine + sessionmaker.
  - `dispose_engine()` closes the pool (called at FastAPI shutdown).
  - `get_session()` is the per-request DI provider.

Pool: pool_size=5, max_overflow=10, pool_pre_ping=True. Service layer
owns its own commits (Planning §6); the DI generator only ensures
rollback on a propagating exception.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """Build (or return) the singleton AsyncEngine.

    Called from FastAPI lifespan startup. Idempotent.
    """
    global _engine, _session_factory

    if _engine is None:
        # SQLite (aiosqlite) uses a non-pooling driver in async mode — pool
        # sizing kwargs are ignored at best and raise at worst (forward-risk
        # noted in Stage-5 Self-Review R-3). Only pass pool sizing to drivers
        # that actually pool connections (asyncpg, etc.).
        is_sqlite = settings.database_url.startswith("sqlite+aiosqlite://")
        engine_kwargs: dict = {
            "echo": settings.db_echo,
            "pool_pre_ping": True,
            "future": True,
        }
        if not is_sqlite:
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
        _engine = create_async_engine(settings.database_url, **engine_kwargs)
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine


def get_engine() -> AsyncEngine:
    """Return the live engine; raises if init_engine wasn't called yet."""
    if _engine is None:
        raise RuntimeError(
            "AsyncEngine not initialised — call init_engine(settings) first."
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the live sessionmaker; raises if init_engine wasn't called yet."""
    if _session_factory is None:
        raise RuntimeError(
            "Session factory not initialised — call init_engine(settings) first."
        )
    return _session_factory


async def dispose_engine() -> None:
    """Close the connection pool. Called from FastAPI lifespan shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a per-request AsyncSession.

    Per Planning §6, the service owns its commits. This generator does
    NOT commit; it only ensures rollback on a propagating exception and
    closes the session at the end of the request.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
