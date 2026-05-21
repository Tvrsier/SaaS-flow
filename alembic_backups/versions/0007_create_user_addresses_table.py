"""create user addresses table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


account_type_enum = postgresql.ENUM(
    "privato",
    "libero_professionista",
    "azienda",
    "ditta_individuale",
    "pubblica_amministrazione",
    name="account_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    account_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "user_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("address_label", sa.String(length=64), nullable=False, server_default=sa.text("'primary'")),
        sa.Column("country", sa.String(length=2), nullable=False, server_default=sa.text("'IT'")),
        sa.Column("province", sa.String(length=10), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("street_number", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("address_label <> ''", name="ck_user_addresses_address_label_not_empty"),
    )
    op.create_index("ix_user_addresses_user_id", "user_addresses", ["user_id"], unique=False)
    op.create_index("ix_user_addresses_account_type", "user_addresses", ["account_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_addresses_account_type", table_name="user_addresses")
    op.drop_index("ix_user_addresses_user_id", table_name="user_addresses")
    op.drop_table("user_addresses")
    bind = op.get_bind()
    account_type_enum.drop(bind, checkfirst=True)

