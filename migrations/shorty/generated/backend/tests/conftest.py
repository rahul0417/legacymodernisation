# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: n/a — test scaffolding
# LEGACY: n/a — scaffold
# COMPONENT: tests/conftest
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Shared pytest fixtures for the Shorty test suite.

Backends:
  - Unit:        no DB (encode/formatting/schemas are pure).
  - Integration: SQLite + aiosqlite for default; per-test in-memory DB.
  - Concurrency: PostgreSQL via testcontainers (marker: requires_pg) — wired
                 by Stage 6 TestGen.

`encode_vectors` fixture skips the test if the JSON file still contains
the placeholder marker `__GENERATED_BY_TESTGEN__`.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
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
from app.modules.urls.encode import EncoderConfig
from app.modules.urls.models import Url

pytest_plugins = ["pytest_asyncio"]


_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_VECTORS_FILE = _FIXTURES_DIR / "encode_vectors.json"


# ── Session-scoped event loop (pytest-asyncio) ─────────────────────────────


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Settings + EncoderConfig (session) ──────────────────────────────────────


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Test Settings — hostname=http://test, salt='', padding=3, default chars."""
    return Settings(
        hostname="http://test",
        db_url="sqlite+aiosqlite:///:memory:",
        salt="",
        padding=3,
    )


@pytest.fixture(scope="session")
def encoder_cfg(settings: Settings) -> EncoderConfig:
    """EncoderConfig derived from the test Settings."""
    return settings.encoder_config


# ── Encode vectors loader (skip if placeholder) ─────────────────────────────


@pytest.fixture(scope="session")
def encode_vectors() -> dict:
    """Load encode_vectors.json; skip the test if Stage 6 has not regenerated."""
    if not _VECTORS_FILE.exists():
        pytest.skip(f"encode_vectors.json not found at {_VECTORS_FILE}")
    data = json.loads(_VECTORS_FILE.read_text(encoding="utf-8"))
    if data.get("__GENERATED_BY_TESTGEN__"):
        pytest.skip(
            "encode_vectors.json is the CodeGen placeholder; "
            "Stage 6 TestGen has not yet regenerated from legacy PHP."
        )
    return data


# ── Async DB engine + session (SQLite in-memory) ────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncIterator:
    """Per-test SQLite engine — schema bootstrapped via create_all.

    Uses a tempfile-backed SQLite (one per test) rather than `:memory:`.
    Rationale: `:memory:` with `StaticPool` shares a single DBAPI connection
    across sessions, which in async + multi-session scenarios (notably
    fire-and-forget telemetry — _record_hit opening its own session
    concurrent with the request session) results in writes from the
    background task not being visible to subsequent read sessions. A
    tempfile-backed DB has standard async-safe multi-connection semantics
    and the runtime cost is negligible at this scale (~110 tests).
    """
    # Import models so they register against Base.metadata before create_all.
    from app.modules.urls import models  # noqa: F401

    fd, db_path = tempfile.mkstemp(prefix="shorty-test-", suffix=".db")
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
    """Per-test async session — committed/rolled back at exit."""
    async with db_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ── App + client fixtures (used once router/main exist) ─────────────────────


@pytest_asyncio.fixture(scope="function")
async def app_instance(settings: Settings, db_session_factory):
    """Build a FastAPI app wired to the per-test SQLite engine.

    ASGITransport does not trigger FastAPI's lifespan, so the dependency
    singletons (`Settings`, `UrlService`) never initialise via the normal
    lifespan path. We override the relevant `Depends()` providers directly
    so tests own their state — no module-level singleton mutation.
    """
    import logging

    from app.db.engine import get_db_session
    from app.main import create_app
    from app.modules.urls.dependencies import get_settings, get_url_service
    from app.modules.urls.service import UrlService

    application = create_app(settings)

    # Build a UrlService bound to the test's session_factory. _record_hit's
    # background task uses this factory, so telemetry writes land in the
    # SAME in-memory DB the test reads from.
    test_service = UrlService(
        cfg=settings.encoder_config,
        hostname=settings.hostname,
        logger=logging.getLogger("shorty.urls.service.test"),
        session_factory=db_session_factory,
    )

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_db_session] = _override_get_db
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_url_service] = lambda: test_service
    return application


@pytest_asyncio.fixture(scope="function")
async def client(app_instance) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient wrapping the ASGI app."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Seeded canonical rows (Planning §11.3 / dual-run/seed.sql parity) ───────


# Canonical seed payload — identical IDs/URLs to dual-run/seed.sql so a single
# fixture spec drives both unit/integration tests and the parity harness.
# IDs cover the encoder's interesting branches: single-char, multi-char,
# 3-digit boundary, mid-range, and near INT32 ceiling.
SEEDED_ROWS: tuple[dict, ...] = (
    {"id": 1,          "url": "https://example.com/alpha",
     "hits": 0,  "accessed": None},
    {"id": 42,         "url": "https://example.com/forty-two",
     "hits": 17, "accessed": datetime(2026, 5, 14, 0, 30, tzinfo=timezone.utc)},
    {"id": 999,        "url": "https://example.com/nine-nine-nine",
     "hits": 0,  "accessed": None},
    {"id": 12345,      "url": "https://example.com/twelve-thousand",
     "hits": 3,  "accessed": datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc)},
    {"id": 2000000000, "url": "https://example.com/two-billion-ceiling",
     "hits": 0,  "accessed": None},
)


@pytest_asyncio.fixture(scope="function")
async def seeded_urls(db_session) -> list[Url]:
    """Insert canonical fixture rows and return them ordered by id.

    Per Planning §11.3, this is the shared seed fixture for tests that need
    deterministic pre-existing rows. The IDs and URLs mirror
    `migrations/shorty/dual-run/seed.sql` so the same data drives both the
    unit/integration suite and the dual-run parity harness.

    The model uses `Identity(always=True)` which on PostgreSQL would reject
    explicit `id` values without `OVERRIDING SYSTEM VALUE`. On SQLite (the
    default test backend) AUTOINCREMENT honours explicit `id`. For Postgres
    parity-run, an analogous fixture overlays the schema with seed.sql.
    """
    from sqlalchemy import insert as _insert

    # Issue one INSERT per row to keep the dialect-agnostic surface minimal.
    for payload in SEEDED_ROWS:
        await db_session.execute(_insert(Url).values(**payload))
    await db_session.commit()

    return list(SEEDED_ROWS)  # type: ignore[return-value]
