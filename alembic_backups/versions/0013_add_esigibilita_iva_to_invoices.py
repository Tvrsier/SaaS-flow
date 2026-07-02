"""add esigibilita_iva to invoices and passive_invoices

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-02 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type
    op.execute("CREATE TYPE esigibilita_iva_type AS ENUM ('I', 'D', 'S')")

    op.add_column(
        "invoices",
        sa.Column(
            "esigibilita_iva",
            sa.Enum("I", "D", "S", name="esigibilita_iva_type"),
            nullable=True,
        ),
    )

    op.add_column(
        "passive_invoices",
        sa.Column(
            "esigibilita_iva",
            sa.Enum("I", "D", "S", name="esigibilita_iva_type"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("passive_invoices", "esigibilita_iva")
    op.drop_column("invoices", "esigibilita_iva")
    op.execute("DROP TYPE esigibilita_iva_type")
