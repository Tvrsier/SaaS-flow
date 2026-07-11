from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import Invoice


class InvoiceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_number_for_company(self, *, company_id: UUID, invoice_number: str) -> Invoice | None:
        return self.session.scalar(
            select(Invoice).where(
                Invoice.company_id == company_id,
                Invoice.invoice_number == invoice_number,
                Invoice.deleted_at.is_(None),
            )
        )
