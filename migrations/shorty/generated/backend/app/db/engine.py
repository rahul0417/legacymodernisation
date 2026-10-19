# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: n/a — infrastructure
# LEGACY: source/shorty.php:218-263 (PDO connection lifecycle)
# COMPONENT: db/engine
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Async engine + session factory + FastAPI request dependency.

Lifetime:
  - `init_engine(settings)` builds the global AsyncEngine + sessionmaker.
  - `dispose_engine()` closes the pool (called at FastAPI shutdown).
  - `get_db_session()` is the per-request DI provider.

Pool: pool_size=5, max_overflow=10, pool_pre_ping=True.
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
        _engine = create_async_engine(
            settings.db_url,
            echo=settings.db_echo,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            future=True,
        )
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


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a per-request AsyncSession.

    Per Planning §7.1, the **service** owns its commit (see
    `UrlService.create_or_get` and `UrlService._record_hit`). The generator
    therefore does **not** commit; it only ensures rollback on a propagating
    exception and closes the session at the end of the request.

    Self-Review §10 recommendation 1 (resolved Stage 6 TestGen, 2026-05-14):
    the prior unconditional `await session.commit()` was a no-op on the
    happy path (service had already committed) but contradicted the
    "service-commits" invariant from Planning §7.1.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
