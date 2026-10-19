# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: n/a — scaffolding
# LEGACY: n/a — scaffold
# COMPONENT: db/base
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
SQLAlchemy 2.x DeclarativeBase.

Single Base class for the engagement. Models import from here, and Alembic
discovers `Base.metadata` from this module.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common declarative base for all ORM models."""

    pass
