# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-05, BR-C-10, BR-C-11
# LEGACY: source/shorty.php (class Shorty), source/database.sql
# COMPONENT: modules/urls/models
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
SQLAlchemy 2.x ORM model for the `urls` table.

Single entity; PostgreSQL DDL is the contract (comprehension §7.1).
SQLite compatibility note: Identity(always=True) maps to AUTOINCREMENT
on SQLite via SQLAlchemy's dialect translation, so this model runs on
both backends without modification.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class Url(Base):
    """A single shortened URL record."""

    __tablename__ = "urls"

    # TODO(stage5-review): Phase 5 upgrade to BIGINT (Gate 1 OQ-03)
    id: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    accessed: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    hits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    __table_args__ = (
        UniqueConstraint("url", name="urls_url_unique"),
        CheckConstraint("hits >= 0", name="urls_hits_nonneg"),
        Index("urls_url_idx", "url"),
    )

    def __repr__(self) -> str:
        # NEVER include self.url in repr — logs must not leak URLs.
        return f"Url(id={self.id!r}, hits={self.hits!r})"
