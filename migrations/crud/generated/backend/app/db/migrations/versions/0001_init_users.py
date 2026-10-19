# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
# LEGACY: source/database.sql
# COMPONENT: db/migrations/versions/0001_init_users
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""Initial schema — users table per Comprehension §6.1 / Planning §3.

Revision ID: 0001_init_users
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "age >= 0 AND age <= 150", name="ck_users_age_range"
        ),
    )


def downgrade() -> None:
    op.drop_table("users")
