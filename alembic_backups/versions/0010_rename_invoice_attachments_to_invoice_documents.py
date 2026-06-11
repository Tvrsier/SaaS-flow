"""rename invoice attachments to documents and add SDI metadata

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_invoice_documents_table() -> None:
    op.create_table(
        "invoice_documents",
        sa.Column("id", UUID, primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_id", UUID, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("xml_block", sa.String(length=64), nullable=False, server_default=sa.text("'ALLEGATI'")),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_format", sa.String(length=50), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("hash", sa.String(length=128), nullable=True),
        sa.Column("document_number", sa.String(length=20), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("reference_line_numbers", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("document_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("include_in_xml", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_invoice_documents_invoice_id", "invoice_documents", ["invoice_id"], unique=False)
    op.create_index("ix_invoice_documents_xml_block", "invoice_documents", ["xml_block"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("invoice_attachments") and not inspector.has_table("invoice_documents"):
        op.rename_table("invoice_attachments", "invoice_documents")
        op.execute("ALTER INDEX IF EXISTS ix_invoice_attachments_invoice_id RENAME TO ix_invoice_documents_invoice_id")
        bind = op.get_bind()
        inspector = sa.inspect(bind)

    if not inspector.has_table("invoice_documents"):
        _create_invoice_documents_table()
        return

    columns = _column_names(inspector, "invoice_documents")

    if "included_in_xml" in columns and "include_in_xml" not in columns:
        op.alter_column(
            "invoice_documents",
            "included_in_xml",
            new_column_name="include_in_xml",
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )
        columns.remove("included_in_xml")
        columns.add("include_in_xml")

    if "xml_block" not in columns:
        op.add_column("invoice_documents", sa.Column("xml_block", sa.String(length=64), nullable=False, server_default=sa.text("'ALLEGATI'")))
    if "document_number" not in columns:
        op.add_column("invoice_documents", sa.Column("document_number", sa.String(length=20), nullable=True))
    if "document_date" not in columns:
        op.add_column("invoice_documents", sa.Column("document_date", sa.Date(), nullable=True))
    if "reference_line_numbers" not in columns:
        op.add_column("invoice_documents", sa.Column("reference_line_numbers", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    if "document_metadata" not in columns:
        op.add_column("invoice_documents", sa.Column("document_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    if "include_in_xml" not in columns:
        op.add_column("invoice_documents", sa.Column("include_in_xml", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # I campi file restano compatibili con gli allegati tradizionali, ma diventano opzionali
    for column_name, column_type in [
        ("filename", sa.String(length=255)),
        ("mime_type", sa.String(length=255)),
        ("file_format", sa.String(length=50)),
        ("size_bytes", sa.BigInteger()),
        ("s3_key", sa.String(length=512)),
        ("hash", sa.String(length=128)),
        ("description", sa.Text()),
    ]:
        if column_name in columns:
            op.alter_column("invoice_documents", column_name, existing_type=column_type, nullable=True)

    if "invoice_id" not in columns:
        op.add_column(
            "invoice_documents",
            sa.Column("invoice_id", UUID, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        )

    indexes = {index["name"] for index in inspector.get_indexes("invoice_documents")}
    if "ix_invoice_documents_invoice_id" not in indexes:
        op.create_index("ix_invoice_documents_invoice_id", "invoice_documents", ["invoice_id"], unique=False)
    if "ix_invoice_documents_xml_block" not in indexes:
        op.create_index("ix_invoice_documents_xml_block", "invoice_documents", ["xml_block"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("invoice_documents"):
        indexes = {index["name"] for index in inspector.get_indexes("invoice_documents")}

        if "include_in_xml" in _column_names(inspector, "invoice_documents") and "included_in_xml" not in _column_names(inspector, "invoice_documents"):
            op.alter_column(
                "invoice_documents",
                "include_in_xml",
                new_column_name="included_in_xml",
                existing_type=sa.Boolean(),
                existing_nullable=False,
            )

        for index_name in ["ix_invoice_documents_xml_block", "ix_invoice_documents_invoice_id"]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="invoice_documents")

        for column_name in [
            "document_metadata",
            "reference_line_numbers",
            "document_date",
            "document_number",
            "xml_block",
        ]:
            if column_name in _column_names(inspector, "invoice_documents"):
                op.drop_column("invoice_documents", column_name)

        if "invoice_documents" in inspector.get_table_names() and "invoice_attachments" not in inspector.get_table_names():
            op.rename_table("invoice_documents", "invoice_attachments")
            op.execute("ALTER INDEX IF EXISTS ix_invoice_documents_invoice_id RENAME TO ix_invoice_attachments_invoice_id")
            return

    if inspector.has_table("invoice_attachments"):
        # Riporta la tabella allo schema legacy più vicino possibile
        legacy_columns = _column_names(inspector, "invoice_attachments")
        if "included_in_xml" in legacy_columns:
            op.alter_column(
                "invoice_attachments",
                "included_in_xml",
                existing_type=sa.Boolean(),
                nullable=False,
            )
        for column_name in ["filename", "mime_type", "file_format", "size_bytes", "s3_key", "hash", "description"]:
            if column_name in legacy_columns:
                op.alter_column("invoice_attachments", column_name, nullable=False if column_name != "description" else True)


