# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-11
# LEGACY: source/database.sql
# COMPONENT: db/migrations/versions/0001_init_urls
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""Initial schema — urls table per comprehension §7.1.

Revision ID: 0001_init_urls
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init_urls"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "accessed",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "hits",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.UniqueConstraint("url", name="urls_url_unique"),
        sa.CheckConstraint("hits >= 0", name="urls_hits_nonneg"),
    )
    op.create_index("urls_url_idx", "urls", ["url"])


def downgrade() -> None:
    op.drop_index("urls_url_idx", table_name="urls")
    op.drop_table("urls")
