"""remove gen_random_uuid default from users.id

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14 00:00:00.000001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "id",
        existing_type=PG_UUID(as_uuid=True),
        server_default=None,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "id",
        existing_type=PG_UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        existing_nullable=False,
    )
