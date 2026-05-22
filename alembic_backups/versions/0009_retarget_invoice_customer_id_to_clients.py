"""retarget invoice customer_id to clients

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_customer_id_fkey")
    op.execute("UPDATE invoices SET customer_id = client_id WHERE customer_id IS NULL AND client_id IS NOT NULL")
    op.execute(
        "ALTER TABLE invoices ADD CONSTRAINT invoices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES clients(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_customer_id_fkey")
    op.execute(
        "ALTER TABLE invoices ADD CONSTRAINT invoices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE SET NULL"
    )
