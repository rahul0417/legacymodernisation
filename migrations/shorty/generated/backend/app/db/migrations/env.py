# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: n/a — infrastructure
# LEGACY: source/database.sql
# COMPONENT: db/migrations/env
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Alembic env script — async-aware.

Runs migrations against the async DSN configured in alembic.ini /
SHORTY_DB_URL. Imports `app.db.base.Base.metadata` so autogenerate works
once we add more models in Phase 5.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure model metadata is registered.
from app.db.base import Base
from app.modules.urls import models  # noqa: F401 — register Url against Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# alembic.ini ships with `sqlalchemy.url = ${SHORTY_DB_URL}`; configparser
# does NOT auto-expand env vars, so override here from the environment when
# present. This is the path used by the docker-compose harness and by any
# CI/CD that exports SHORTY_DB_URL.
_env_db_url = os.environ.get("SHORTY_DB_URL")
if _env_db_url:
    config.set_main_option("sqlalchemy.url", _env_db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live connection — emits SQL statements."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
