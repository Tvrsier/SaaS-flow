"""drop duplicated invoice party columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


INVOICE_PARTY_COLUMNS = [
    "customer_name",
    "customer_vat_number",
    "customer_tax_code",
    "customer_address",
    "customer_city",
    "customer_postal_code",
    "customer_province",
    "customer_country",
    "customer_pec",
    "customer_recipient_code",
    "supplier_name",
    "supplier_vat_number",
    "supplier_tax_code",
    "supplier_address",
    "supplier_city",
    "supplier_postal_code",
    "supplier_province",
    "supplier_country",
]


def upgrade() -> None:
    for column_name in reversed(INVOICE_PARTY_COLUMNS):
        op.drop_column("invoices", column_name)


def downgrade() -> None:
    op.add_column("invoices", sa.Column("customer_name", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("customer_vat_number", sa.String(length=32), nullable=True))
    op.add_column("invoices", sa.Column("customer_tax_code", sa.String(length=32), nullable=True))
    op.add_column("invoices", sa.Column("customer_address", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("customer_city", sa.String(length=120), nullable=True))
    op.add_column("invoices", sa.Column("customer_postal_code", sa.String(length=12), nullable=True))
    op.add_column("invoices", sa.Column("customer_province", sa.String(length=2), nullable=True))
    op.add_column("invoices", sa.Column("customer_country", sa.String(length=2), nullable=True))
    op.add_column("invoices", sa.Column("customer_pec", sa.String(length=256), nullable=True))
    op.add_column("invoices", sa.Column("customer_recipient_code", sa.String(length=7), nullable=True))
    op.add_column("invoices", sa.Column("supplier_name", sa.String(length=255), nullable=False))
    op.add_column("invoices", sa.Column("supplier_vat_number", sa.String(length=32), nullable=False))
    op.add_column("invoices", sa.Column("supplier_tax_code", sa.String(length=32), nullable=True))
    op.add_column("invoices", sa.Column("supplier_address", sa.String(length=255), nullable=False))
    op.add_column("invoices", sa.Column("supplier_city", sa.String(length=120), nullable=False))
    op.add_column("invoices", sa.Column("supplier_postal_code", sa.String(length=12), nullable=False))
    op.add_column("invoices", sa.Column("supplier_province", sa.String(length=2), nullable=True))
    op.add_column("invoices", sa.Column("supplier_country", sa.String(length=2), nullable=False))
