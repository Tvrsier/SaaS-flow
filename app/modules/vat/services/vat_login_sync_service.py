"""VAT sync routines executed at user login."""
from __future__ import annotations

import logging
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import Invoice, VatPeriod
from app.modules.invoices.domain.enums import InvoiceStatus
from app.modules.vat.services.vat_movement_service import VatMovementService
from app.modules.vat.services.vat_period_service import VatPeriodService
from app.modules.vat.services.vat_summary_service import VatSummaryService

logger = logging.getLogger("GestPro")

VatFrequency = Literal["MONTHLY", "QUARTERLY"]


class VatLoginSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.movement_service = VatMovementService(db)
        self.period_service = VatPeriodService(db)
        self.summary_service = VatSummaryService(db)

    def sync_company_vat(self, company_id: UUID, target_date: date | None = None, frequency: VatFrequency = "QUARTERLY") -> None:
        as_of = target_date or date.today()

        self.period_service.get_or_create_period(
            company_id=company_id,
            competence_date=as_of,
            frequency=frequency,
        )
        self._align_active_invoices(company_id=company_id, as_of=as_of)
        self._close_expired_periods(company_id=company_id, as_of=as_of, frequency=frequency)

    def _align_active_invoices(self, company_id: UUID, as_of: date) -> None:
        invoice_ids = self.db.scalars(
            select(Invoice.id)
            .where(
                Invoice.company_id == company_id,
                Invoice.deleted_at.is_(None),
                Invoice.status.in_((InvoiceStatus.READY, InvoiceStatus.ISSUED)),
                Invoice.issue_date <= as_of,
            )
            .order_by(Invoice.issue_date.asc(), Invoice.created_at.asc())
        ).all()

        aligned = 0
        skipped = 0
        for invoice_id in invoice_ids:
            try:
                self.movement_service.replace_for_active_invoice(invoice_id)
                aligned += 1
            except ValueError:
                skipped += 1

        if aligned or skipped:
            logger.info(
                "VAT login alignment for company %s: aligned=%s skipped=%s",
                company_id,
                aligned,
                skipped,
            )

    def _close_expired_periods(self, company_id: UUID, as_of: date, frequency: VatFrequency) -> None:
        expired_open_periods = self.db.scalars(
            select(VatPeriod)
            .where(
                VatPeriod.company_id == company_id,
                VatPeriod.frequency == frequency,
                VatPeriod.status == "OPEN",
                VatPeriod.end_date < as_of,
            )
            .order_by(VatPeriod.year.asc(), VatPeriod.period_index.asc())
        ).all()

        for period in expired_open_periods:
            existing_settlement = self.summary_service.get_settlement_by_period(
                company_id=company_id,
                period_id=period.id,
            )
            if existing_settlement is None:
                self.summary_service.close_period_and_create_settlement(
                    company_id=company_id,
                    period_id=period.id,
                )
