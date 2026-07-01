"""create passive invoices and vat tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-19 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create passive_invoices table
    op.create_table(
        "passive_invoices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_vat_number", sa.String(length=20), nullable=True),
        sa.Column("supplier_tax_code", sa.String(length=20), nullable=True),
        sa.Column("supplier_address", sa.String(length=255), nullable=True),
        sa.Column("supplier_city", sa.String(length=100), nullable=True),
        sa.Column("supplier_postal_code", sa.String(length=20), nullable=True),
        sa.Column("supplier_province", sa.String(length=10), nullable=True),
        sa.Column("supplier_country", sa.String(length=2), nullable=False, server_default=sa.text("'IT'")),
        sa.Column("invoice_number", sa.String(length=20), nullable=False),
        sa.Column("invoice_year", sa.Integer(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("vat_competence_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("document_type", postgresql.ENUM(name="invoice_document_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="invoice_status", create_type=False), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("xml_hash", sa.String(length=128), nullable=True),
        sa.Column("xml_s3_key", sa.String(length=512), nullable=True),
        sa.Column("source_channel", sa.String(length=50), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("taxable_amount >= 0", name="ck_passive_invoices_taxable_amount_non_negative"),
        sa.CheckConstraint("vat_amount >= 0", name="ck_passive_invoices_vat_amount_non_negative"),
        sa.CheckConstraint("total_amount >= 0", name="ck_passive_invoices_total_amount_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_passive_invoices_company_id", "passive_invoices", ["company_id"], unique=False)
    op.create_index("ix_passive_invoices_supplier_id", "passive_invoices", ["supplier_id"], unique=False)
    op.create_index("ix_passive_invoices_invoice_date", "passive_invoices", ["invoice_date"], unique=False)
    op.create_index("ix_passive_invoices_registration_date", "passive_invoices", ["registration_date"], unique=False)
    op.create_index("ix_passive_invoices_vat_competence_date", "passive_invoices", ["vat_competence_date"], unique=False)
    op.create_index("ix_passive_invoices_status", "passive_invoices", ["status"], unique=False)
    op.create_index("ix_passive_invoices_xml_hash", "passive_invoices", ["xml_hash"], unique=False)

    # Create passive_invoice_lines table
    op.create_table(
        "passive_invoice_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("passive_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("passive_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_nature", postgresql.ENUM(name="invoice_vat_nature", create_type=False), nullable=True),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("line_number > 0", name="ck_passive_invoice_lines_line_number_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_passive_invoice_lines_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_passive_invoice_lines_unit_price_non_negative"),
        sa.CheckConstraint("COALESCE(discount_amount, 0) >= 0", name="ck_passive_invoice_lines_discount_amount_non_negative"),
        sa.CheckConstraint("COALESCE(discount_percentage, 0) >= 0 AND COALESCE(discount_percentage, 0) <= 100", name="ck_passive_invoice_lines_discount_percentage_range"),
        sa.CheckConstraint("vat_rate >= 0", name="ck_passive_invoice_lines_vat_rate_non_negative"),
        sa.CheckConstraint("taxable_amount >= 0", name="ck_passive_invoice_lines_taxable_amount_non_negative"),
        sa.CheckConstraint("vat_amount >= 0", name="ck_passive_invoice_lines_vat_amount_non_negative"),
        sa.CheckConstraint("total_amount >= 0", name="ck_passive_invoice_lines_total_amount_non_negative"),
        sa.UniqueConstraint("passive_invoice_id", "line_number", name="uq_passive_invoice_lines_invoice_line_number"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_passive_invoice_lines_passive_invoice_id", "passive_invoice_lines", ["passive_invoice_id"], unique=False)

    # Create passive_invoice_vat_summary table
    op.create_table(
        "passive_invoice_vat_summary",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("passive_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("passive_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_nature", postgresql.ENUM(name="invoice_vat_nature", create_type=False), nullable=True),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_passive_invoice_vat_summary_passive_invoice_id", "passive_invoice_vat_summary", ["passive_invoice_id"], unique=False)
    op.create_unique_constraint(
        "uq_passive_invoice_vat_summary_invoice_rate_nature",
        "passive_invoice_vat_summary",
        ["passive_invoice_id", "vat_rate", "vat_nature"],
    )

    # Create vat_periods table
    op.create_table(
        "vat_periods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("previous_credit", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("period_index > 0", name="ck_vat_periods_period_index_positive"),
        sa.CheckConstraint("(frequency = 'MONTHLY' AND period_index BETWEEN 1 AND 12) OR (frequency = 'QUARTERLY' AND period_index BETWEEN 1 AND 4)", name="ck_vat_periods_period_index_valid"),
        sa.CheckConstraint("previous_credit >= 0", name="ck_vat_periods_previous_credit_non_negative"),
        sa.UniqueConstraint("company_id", "year", "period_index", "frequency", name="uq_vat_periods_company_year_period_frequency"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vat_periods_company_id", "vat_periods", ["company_id"], unique=False)
    op.create_index("ix_vat_periods_status", "vat_periods", ["status"], unique=False)
    op.create_index("ix_vat_periods_company_year_frequency", "vat_periods", ["company_id", "year", "frequency"], unique=False)

    # Create vat_movements table
    op.create_table(
        "vat_movements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vat_periods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_passive_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("passive_invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("vat_competence_date", sa.Date(), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_nature", postgresql.ENUM(name="invoice_vat_nature", create_type=False), nullable=True),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("vat_rate >= 0", name="ck_vat_movements_vat_rate_non_negative"),
        sa.CheckConstraint("taxable_amount >= 0", name="ck_vat_movements_taxable_amount_non_negative"),
        sa.CheckConstraint("vat_amount >= 0", name="ck_vat_movements_vat_amount_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vat_movements_company_id", "vat_movements", ["company_id"], unique=False)
    op.create_index("ix_vat_movements_period_id", "vat_movements", ["period_id"], unique=False)
    op.create_index("ix_vat_movements_source_type", "vat_movements", ["source_type"], unique=False)
    op.create_index("ix_vat_movements_movement_type", "vat_movements", ["movement_type"], unique=False)
    op.create_index("ix_vat_movements_vat_competence_date", "vat_movements", ["vat_competence_date"], unique=False)
    op.create_index("ix_vat_movements_source_invoice_id", "vat_movements", ["source_invoice_id"], unique=False)
    op.create_index("ix_vat_movements_source_passive_invoice_id", "vat_movements", ["source_passive_invoice_id"], unique=False)

    # Create vat_settlements table
    op.create_table(
        "vat_settlements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vat_periods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("total_debit", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_credit", sa.Numeric(18, 2), nullable=False),
        sa.Column("previous_credit", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_to_pay", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit_to_carry", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("payment_status", sa.String(length=20), nullable=False, server_default=sa.text("'UNPAID'")),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("payment_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("total_debit >= 0", name="ck_vat_settlements_total_debit_non_negative"),
        sa.CheckConstraint("total_credit >= 0", name="ck_vat_settlements_total_credit_non_negative"),
        sa.CheckConstraint("previous_credit >= 0", name="ck_vat_settlements_previous_credit_non_negative"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_vat_settlements_amount_paid_non_negative"),
        sa.CheckConstraint("credit_to_carry >= 0", name="ck_vat_settlements_credit_to_carry_non_negative"),
        sa.UniqueConstraint("period_id", name="uq_vat_settlements_period_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vat_settlements_company_id", "vat_settlements", ["company_id"], unique=False)
    op.create_index("ix_vat_settlements_period_id", "vat_settlements", ["period_id"], unique=False)
    op.create_index("ix_vat_settlements_payment_status", "vat_settlements", ["payment_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vat_settlements_payment_status", table_name="vat_settlements")
    op.drop_index("ix_vat_settlements_period_id", table_name="vat_settlements")
    op.drop_index("ix_vat_settlements_company_id", table_name="vat_settlements")
    op.drop_table("vat_settlements")

    op.drop_index("ix_vat_movements_source_passive_invoice_id", table_name="vat_movements")
    op.drop_index("ix_vat_movements_source_invoice_id", table_name="vat_movements")
    op.drop_index("ix_vat_movements_vat_competence_date", table_name="vat_movements")
    op.drop_index("ix_vat_movements_movement_type", table_name="vat_movements")
    op.drop_index("ix_vat_movements_source_type", table_name="vat_movements")
    op.drop_index("ix_vat_movements_period_id", table_name="vat_movements")
    op.drop_index("ix_vat_movements_company_id", table_name="vat_movements")
    op.drop_table("vat_movements")

    op.drop_index("ix_vat_periods_company_year_frequency", table_name="vat_periods")
    op.drop_index("ix_vat_periods_status", table_name="vat_periods")
    op.drop_index("ix_vat_periods_company_id", table_name="vat_periods")
    op.drop_table("vat_periods")

    op.drop_constraint("uq_passive_invoice_vat_summary_invoice_rate_nature", table_name="passive_invoice_vat_summary", type_="unique")
    op.drop_index("ix_passive_invoice_vat_summary_passive_invoice_id", table_name="passive_invoice_vat_summary")
    op.drop_table("passive_invoice_vat_summary")

    op.drop_index("ix_passive_invoice_lines_passive_invoice_id", table_name="passive_invoice_lines")
    op.drop_table("passive_invoice_lines")

    op.drop_index("ix_passive_invoices_xml_hash", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_status", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_vat_competence_date", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_registration_date", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_invoice_date", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_supplier_id", table_name="passive_invoices")
    op.drop_index("ix_passive_invoices_company_id", table_name="passive_invoices")
    op.drop_table("passive_invoices")
