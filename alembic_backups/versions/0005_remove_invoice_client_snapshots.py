"""remove client snapshots from invoices

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


SNAPSHOT_COLUMNS = [
    "client_type_snapshot",
    "client_first_name_snapshot",
    "client_last_name_snapshot",
    "client_company_name_snapshot",
    "client_vat_number_snapshot",
    "client_tax_code_snapshot",
    "client_address_snapshot",
    "client_city_snapshot",
    "client_postal_code_snapshot",
    "client_province_snapshot",
    "client_country_snapshot",
    "client_pec_snapshot",
    "client_recipient_code_snapshot",
]


def upgrade() -> None:
    for column_name in reversed(SNAPSHOT_COLUMNS):
        op.drop_column("invoices", column_name)


def downgrade() -> None:
    op.add_column("invoices", sa.Column("client_type_snapshot", sa.String(length=30), nullable=True))
    op.add_column("invoices", sa.Column("client_first_name_snapshot", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("client_last_name_snapshot", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("client_company_name_snapshot", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("client_vat_number_snapshot", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("client_tax_code_snapshot", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("client_address_snapshot", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("client_city_snapshot", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("client_postal_code_snapshot", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("client_province_snapshot", sa.String(length=10), nullable=True))
    op.add_column("invoices", sa.Column("client_country_snapshot", sa.String(length=2), nullable=True))
    op.add_column("invoices", sa.Column("client_pec_snapshot", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("client_recipient_code_snapshot", sa.String(length=7), nullable=True))