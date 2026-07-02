"""add user payment profiles and invoice payment details

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-02 16:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_payment_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method", postgresql.ENUM(name="invoice_payment_method", create_type=False), nullable=False),
        sa.Column("beneficiary", sa.String(length=200), nullable=True),
        sa.Column("financial_institution", sa.String(length=200), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("abi", sa.String(length=5), nullable=True),
        sa.Column("cab", sa.String(length=5), nullable=True),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column("payment_code", sa.String(length=60), nullable=True),
        sa.Column("postal_office_code", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "payment_method", name="uq_user_payment_profiles_user_method"),
    )
    op.create_index("ix_user_payment_profiles_user_id", "user_payment_profiles", ["user_id"], unique=False)

    op.create_table(
        "invoice_payment_details",
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("beneficiary", sa.String(length=200), nullable=True),
        sa.Column("financial_institution", sa.String(length=200), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("abi", sa.String(length=5), nullable=True),
        sa.Column("cab", sa.String(length=5), nullable=True),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column("payment_code", sa.String(length=60), nullable=True),
        sa.Column("postal_office_code", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("invoice_id"),
    )


def downgrade() -> None:
    op.drop_table("invoice_payment_details")
    op.drop_index("ix_user_payment_profiles_user_id", table_name="user_payment_profiles")
    op.drop_table("user_payment_profiles")
