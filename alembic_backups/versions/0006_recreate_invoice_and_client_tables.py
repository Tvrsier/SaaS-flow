"""recreate missing invoice and client tables after manual cleanup

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


client_type_enum = postgresql.ENUM(
    "PRIVATE",
    "COMPANY",
    "PUBLIC_ADMINISTRATION",
    name="client_type",
    create_type=False,
)

invoice_document_type_enum = postgresql.ENUM(
    "TD01",
    "TD02",
    "TD03",
    "TD04",
    "TD05",
    "TD06",
    "TD07",
    "TD08",
    "TD09",
    "TD16",
    "TD17",
    "TD18",
    "TD19",
    "TD20",
    "TD21",
    "TD22",
    "TD23",
    "TD24",
    "TD25",
    "TD26",
    "TD27",
    "TD28",
    "TD29",
    name="invoice_document_type",
    create_type=False,
)

invoice_status_enum = postgresql.ENUM(
    "DRAFT",
    "READY",
    "ISSUED",
    "CANCELLED",
    name="invoice_status",
    create_type=False,
)

invoice_payment_method_enum = postgresql.ENUM(
    "MP01",
    "MP02",
    "MP03",
    "MP04",
    "MP05",
    "MP06",
    "MP07",
    "MP08",
    "MP09",
    "MP10",
    "MP11",
    "MP12",
    "MP13",
    "MP14",
    "MP15",
    "MP16",
    "MP17",
    "MP18",
    "MP19",
    "MP20",
    "MP21",
    "MP22",
    "MP23",
    name="invoice_payment_method",
    create_type=False,
)

invoice_payment_status_enum = postgresql.ENUM(
    "PENDING",
    "PARTIAL",
    "PAID",
    "CANCELLED",
    name="invoice_payment_status",
    create_type=False,
)

invoice_vat_nature_enum = postgresql.ENUM(
    "N1",
    "N2.1",
    "N2.2",
    "N3.1",
    "N3.2",
    "N3.3",
    "N3.4",
    "N3.5",
    "N3.6",
    "N4",
    "N5",
    "N6.1",
    "N6.2",
    "N6.3",
    "N6.4",
    "N6.5",
    "N6.6",
    "N6.7",
    "N6.8",
    "N6.9",
    "N7",
    name="invoice_vat_nature",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    client_type_enum.create(bind, checkfirst=True)
    invoice_document_type_enum.create(bind, checkfirst=True)
    invoice_status_enum.create(bind, checkfirst=True)
    invoice_payment_method_enum.create(bind, checkfirst=True)
    invoice_payment_status_enum.create(bind, checkfirst=True)
    invoice_vat_nature_enum.create(bind, checkfirst=True)

    if not inspector.has_table("clients"):
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
        )
        op.create_index("ix_clients_company_id", "clients", ["company_id"], unique=False)
        op.create_index("ix_clients_client_type", "clients", ["client_type"], unique=False)
        op.create_index("ix_clients_deleted_at", "clients", ["deleted_at"], unique=False)

    if not inspector.has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
            sa.Column("customer_name", sa.String(length=255), nullable=True),
            sa.Column("customer_vat_number", sa.String(length=32), nullable=True),
            sa.Column("customer_tax_code", sa.String(length=32), nullable=True),
            sa.Column("customer_address", sa.String(length=255), nullable=True),
            sa.Column("customer_city", sa.String(length=120), nullable=True),
            sa.Column("customer_postal_code", sa.String(length=12), nullable=True),
            sa.Column("customer_province", sa.String(length=2), nullable=True),
            sa.Column("customer_country", sa.String(length=2), nullable=True),
            sa.Column("customer_pec", sa.String(length=256), nullable=True),
            sa.Column("customer_recipient_code", sa.String(length=7), nullable=True),
            sa.Column("supplier_name", sa.String(length=255), nullable=False),
            sa.Column("supplier_vat_number", sa.String(length=32), nullable=False),
            sa.Column("supplier_tax_code", sa.String(length=32), nullable=True),
            sa.Column("supplier_address", sa.String(length=255), nullable=False),
            sa.Column("supplier_city", sa.String(length=120), nullable=False),
            sa.Column("supplier_postal_code", sa.String(length=12), nullable=False),
            sa.Column("supplier_province", sa.String(length=2), nullable=True),
            sa.Column("supplier_country", sa.String(length=2), nullable=False),
            sa.Column("invoice_number", sa.String(length=20), nullable=True),
            sa.Column("invoice_year", sa.Integer(), nullable=False),
            sa.Column("invoice_section", sa.String(length=20), nullable=True),
            sa.Column("document_type", invoice_document_type_enum, nullable=False),
            sa.Column("status", invoice_status_enum, nullable=False, server_default=sa.text("'DRAFT'")),
            sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'EUR'")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("withholding_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("stamp_duty_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("rounding_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("xml_s3_key", sa.String(length=512), nullable=True),
            sa.Column("xml_hash", sa.String(length=128), nullable=True),
            sa.Column("xml_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("schema_version", sa.String(length=32), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.CheckConstraint("status = 'DRAFT' OR invoice_number IS NOT NULL", name="ck_invoices_invoice_number_required"),
            sa.CheckConstraint("taxable_amount >= 0", name="ck_invoices_taxable_amount_non_negative"),
            sa.CheckConstraint("vat_amount >= 0", name="ck_invoices_vat_amount_non_negative"),
            sa.CheckConstraint("total_amount >= 0", name="ck_invoices_total_amount_non_negative"),
            sa.CheckConstraint("withholding_amount >= 0", name="ck_invoices_withholding_amount_non_negative"),
            sa.CheckConstraint("stamp_duty_amount >= 0", name="ck_invoices_stamp_duty_amount_non_negative"),
        )
        op.create_index("ix_invoices_company_id", "invoices", ["company_id"], unique=False)
        op.create_index("ix_invoices_client_id", "invoices", ["client_id"], unique=False)
        op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"], unique=False)
        op.create_index("ix_invoices_issue_date", "invoices", ["issue_date"], unique=False)
        op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)
        op.create_index(
            "ux_invoices_company_year_section_number_active",
            "invoices",
            ["company_id", "invoice_year", "invoice_section", "invoice_number"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    if not inspector.has_table("invoice_lines"):
        op.create_table(
            "invoice_lines",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("line_number", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(length=1000), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
            sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
            sa.Column("discount_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
            sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
            sa.Column("vat_nature", invoice_vat_nature_enum, nullable=True),
            sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("unit_of_measure", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.CheckConstraint("line_number > 0", name="ck_invoice_lines_line_number_positive"),
            sa.CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
            sa.CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price_non_negative"),
            sa.CheckConstraint("COALESCE(discount_amount, 0) >= 0", name="ck_invoice_lines_discount_amount_non_negative"),
            sa.CheckConstraint("COALESCE(discount_percentage, 0) >= 0 AND COALESCE(discount_percentage, 0) <= 100", name="ck_invoice_lines_discount_percentage_range"),
            sa.CheckConstraint("vat_rate >= 0", name="ck_invoice_lines_vat_rate_non_negative"),
            sa.CheckConstraint("taxable_amount >= 0", name="ck_invoice_lines_taxable_amount_non_negative"),
            sa.CheckConstraint("vat_amount >= 0", name="ck_invoice_lines_vat_amount_non_negative"),
            sa.CheckConstraint("total_amount >= 0", name="ck_invoice_lines_total_amount_non_negative"),
            sa.UniqueConstraint("invoice_id", "line_number", name="uq_invoice_lines_invoice_line_number"),
        )
        op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"], unique=False)

    if not inspector.has_table("invoice_vat_summary"):
        op.create_table(
            "invoice_vat_summary",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
            sa.Column("vat_nature", invoice_vat_nature_enum, nullable=True),
            sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_invoice_vat_summary_invoice_id", "invoice_vat_summary", ["invoice_id"], unique=False)
        op.create_unique_constraint(
            "uq_invoice_vat_summary_invoice_rate_nature",
            "invoice_vat_summary",
            ["invoice_id", "vat_rate", "vat_nature"],
        )

    if not inspector.has_table("invoice_payments"):
        op.create_table(
            "invoice_payments",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payment_method", invoice_payment_method_enum, nullable=False),
            sa.Column("payment_status", invoice_payment_status_enum, nullable=False, server_default=sa.text("'PENDING'")),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("iban", sa.String(length=34), nullable=True),
            sa.Column("reference", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.CheckConstraint("amount >= 0", name="ck_invoice_payments_amount_non_negative"),
            sa.CheckConstraint("paid_amount >= 0", name="ck_invoice_payments_paid_amount_non_negative"),
            sa.CheckConstraint("paid_amount <= amount", name="ck_invoice_payments_paid_amount_not_exceed_amount"),
        )
        op.create_index("ix_invoice_payments_invoice_id", "invoice_payments", ["invoice_id"], unique=False)

    if not inspector.has_table("invoice_attachments"):
        op.create_table(
            "invoice_attachments",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=255), nullable=False),
            sa.Column("file_format", sa.String(length=50), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("s3_key", sa.String(length=512), nullable=False),
            sa.Column("hash", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("included_in_xml", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_invoice_attachments_invoice_id", "invoice_attachments", ["invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invoice_attachments_invoice_id", table_name="invoice_attachments")
    op.drop_table("invoice_attachments")

    op.drop_index("ix_invoice_payments_invoice_id", table_name="invoice_payments")
    op.drop_table("invoice_payments")

    op.drop_constraint("uq_invoice_vat_summary_invoice_rate_nature", table_name="invoice_vat_summary", type_="unique")
    op.drop_index("ix_invoice_vat_summary_invoice_id", table_name="invoice_vat_summary")
    op.drop_table("invoice_vat_summary")

    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")

    op.drop_index("ux_invoices_company_year_section_number_active", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_issue_date", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_client_id", table_name="invoices")
    op.drop_index("ix_invoices_company_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_clients_deleted_at", table_name="clients")
    op.drop_index("ix_clients_client_type", table_name="clients")
    op.drop_index("ix_clients_company_id", table_name="clients")
    op.drop_table("clients")

    bind = op.get_bind()
    invoice_vat_nature_enum.drop(bind, checkfirst=True)
    invoice_payment_status_enum.drop(bind, checkfirst=True)
    invoice_payment_method_enum.drop(bind, checkfirst=True)
    invoice_status_enum.drop(bind, checkfirst=True)
    invoice_document_type_enum.drop(bind, checkfirst=True)
    client_type_enum.drop(bind, checkfirst=True)
