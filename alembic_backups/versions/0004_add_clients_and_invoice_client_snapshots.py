"""add clients table and invoice client snapshots

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


client_type_enum = postgresql.ENUM(
    "PRIVATE",
    "COMPANY",
    "PUBLIC_ADMINISTRATION",
    name="client_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    client_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_type", client_type_enum, nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("vat_number", sa.String(length=20), nullable=True),
        sa.Column("tax_code", sa.String(length=20), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("province", sa.String(length=10), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False, server_default=sa.text("'IT'")),
        sa.Column("pec", sa.String(length=255), nullable=True),
        sa.Column("recipient_code", sa.String(length=7), nullable=True, server_default=sa.text("'0000000'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "client_type <> 'PRIVATE' OR (first_name IS NOT NULL AND last_name IS NOT NULL AND tax_code IS NOT NULL AND vat_number IS NULL AND recipient_code = '0000000')",
            name="ck_clients_private_required_fields",
        ),
        sa.CheckConstraint(
            "client_type <> 'COMPANY' OR (company_name IS NOT NULL AND vat_number IS NOT NULL)",
            name="ck_clients_company_required_fields",
        ),
        sa.CheckConstraint(
            "client_type <> 'PUBLIC_ADMINISTRATION' OR (company_name IS NOT NULL AND tax_code IS NOT NULL AND recipient_code IS NOT NULL AND char_length(recipient_code) = 6)",
            name="ck_clients_pa_required_fields",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_company_id", "clients", ["company_id"], unique=False)
    op.create_index("ix_clients_client_type", "clients", ["client_type"], unique=False)
    op.create_index("ix_clients_deleted_at", "clients", ["deleted_at"], unique=False)

    op.add_column("invoices", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("client_type_snapshot", client_type_enum, nullable=True),
    )
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
    op.create_foreign_key("fk_invoices_client_id_clients", "invoices", "clients", ["client_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_invoices_client_id", "invoices", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invoices_client_id", table_name="invoices")
    op.drop_constraint("fk_invoices_client_id_clients", "invoices", type_="foreignkey")

    op.drop_column("invoices", "client_recipient_code_snapshot")
    op.drop_column("invoices", "client_pec_snapshot")
    op.drop_column("invoices", "client_country_snapshot")
    op.drop_column("invoices", "client_province_snapshot")
    op.drop_column("invoices", "client_postal_code_snapshot")
    op.drop_column("invoices", "client_city_snapshot")
    op.drop_column("invoices", "client_address_snapshot")
    op.drop_column("invoices", "client_tax_code_snapshot")
    op.drop_column("invoices", "client_vat_number_snapshot")
    op.drop_column("invoices", "client_company_name_snapshot")
    op.drop_column("invoices", "client_last_name_snapshot")
    op.drop_column("invoices", "client_first_name_snapshot")
    op.drop_column("invoices", "client_type_snapshot")
    op.drop_column("invoices", "client_id")

    op.drop_index("ix_clients_deleted_at", table_name="clients")
    op.drop_index("ix_clients_client_type", table_name="clients")
    op.drop_index("ix_clients_company_id", table_name="clients")
    op.drop_table("clients")

    bind = op.get_bind()
    client_type_enum.drop(bind, checkfirst=True)
