# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
# LEGACY: source/database.sql:5-11
# COMPONENT: modules/users/models
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
SQLAlchemy 2.x ORM model for the `users` table.

Single entity; PostgreSQL DDL is the contract (Comprehension §6.1).
SQLite compatibility note: Identity(always=True) maps to AUTOINCREMENT
on SQLite via SQLAlchemy's dialect translation, so this model runs on
both backends without modification.

Belt-and-braces invariants at the DB layer (matches Planning §3 / §4):
  - UNIQUE (email)            → BR-C-11
  - CHECK (age BETWEEN 0,150) → BR-C-04
  - VARCHAR(100) on name      → BR-C-06
  - VARCHAR(100) on email     → BR-C-05
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Identity,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """A single user record (BR-C-07: id is the surrogate PK)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    age: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("age >= 0 AND age <= 150", name="ck_users_age_range"),
    )

    def __repr__(self) -> str:
        # email included intentionally for ops debugging (no PII guard in MVP);
        # service layer scrubs it before logging at WARNING.
        return f"<User id={self.id} email={self.email!r}>"
