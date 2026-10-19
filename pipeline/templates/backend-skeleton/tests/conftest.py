# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — test scaffolding
# LEGACY: n/a — scaffold
# COMPONENT: tests/conftest
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Shared pytest fixtures for the CRUD Users test suite.

Backends:
  - Unit:        no DB (schemas tests are pure).
  - Integration: tempfile-backed SQLite + aiosqlite (one DB per test).
  - Postgres:    via testcontainers, marker `requires_pg` (Stage 6).

ASGITransport does not trigger FastAPI's lifespan, so dependency
singletons never initialise via the normal startup path. Tests own
their state via `dependency_overrides`.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.base import Base
from app.modules.users.models import User  # noqa: F401 — register on metadata

pytest_plugins = ["pytest_asyncio"]


# ── Session-scoped event loop (pytest-asyncio) ─────────────────────────────


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Settings (session) ──────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Test Settings — in-memory SQLite + safe defaults."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        cors_origins=["http://localhost:5173"],
    )


# ── Async DB engine + session (tempfile SQLite per test) ────────────────────


@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncIterator:
    """Per-test SQLite engine — schema bootstrapped via create_all.

    Tempfile-backed (NOT :memory:) so multiple session factories built
    over the same engine see the same data. Rationale matches shorty's
    conftest: `:memory:` + StaticPool collapses to a single DBAPI
    connection, which breaks multi-session writes.
    """
    fd, db_path = tempfile.mkstemp(prefix="crud-test-", suffix=".db")
    os.close(fd)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


@pytest_asyncio.fixture(scope="function")
async def db_session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    """An async_sessionmaker bound to the per-test engine."""
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(scope="function")
async def db_session(db_session_factory) -> AsyncIterator[AsyncSession]:
    """Per-test async session — rolled back at exit."""
    async with db_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ── App + client fixtures ───────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def app_instance(settings: Settings, db_session_factory):
    """Build a FastAPI app wired to the per-test SQLite engine.

    Overrides:
      - `get_session` → yields a session bound to the test's factory.
      - `get_user_service` → fresh UserService (no module-level singleton).
    """
    import logging

    from app.db.engine import get_session
    from app.main import create_app
    from app.modules.users.dependencies import get_user_service
    from app.modules.users.service import UserService

    application = create_app(settings)
    test_service = UserService(
        logger=logging.getLogger("crud.users.service.test"),
    )

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_session] = _override_get_session
    application.dependency_overrides[get_user_service] = lambda: test_service
    return application


@pytest_asyncio.fixture(scope="function")
async def client(app_instance) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient wrapping the ASGI app."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Seeded canonical rows (dual-run parity) ─────────────────────────────────

# Canonical seed payload mirrors `migrations/crud/dual-run/seed-pg.sql`
# so a single fixture spec drives both unit/integration tests and the
# Stage 7 dual-run harness.
SEEDED_USERS: tuple[dict, ...] = (
    {"name": "Alice",   "age": 30, "email": "alice@example.com"},
    {"name": "Bob",     "age": 45, "email": "bob@example.com"},
    {"name": "Charlie", "age": 22, "email": "charlie@example.com"},
)


@pytest_asyncio.fixture(scope="function")
async def seeded_users(db_session) -> list[User]:
    """Insert canonical fixture rows and return them ordered by id ASC."""
    from sqlalchemy import insert as _insert

    for payload in SEEDED_USERS:
        await db_session.execute(_insert(User).values(**payload))
    await db_session.commit()

    from sqlalchemy import select as _select

    rows = (
        await db_session.execute(_select(User).order_by(User.id.asc()))
    ).scalars().all()
    return list(rows)
