"""VAT Movement Service"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.invoice import Invoice, InvoiceVatSummary, PassiveInvoice, PassiveInvoiceVatSummary, VatMovement, VatPeriod
from app.modules.invoices.domain.enums import EsigibilitaIVA
from app.modules.vat.services.vat_period_service import VatPeriodService

logger = logging.getLogger("GestPro")

MovementType = Literal["DEBIT", "CREDIT"]
SourceType = Literal["ACTIVE_INVOICE", "PASSIVE_INVOICE", "MANUAL_ADJUSTMENT"]


class VatMovementService:
    def __init__(self, db: Session):
        self.db = db
        self.period_service = VatPeriodService(db)

    def create_from_active_invoice(self, invoice_id: UUID) -> list[VatMovement]:
        """
        Create VAT movements from an active invoice.

        Args:
            invoice_id: Invoice UUID

        Returns:
            List of created VatMovement instances

        Raises:
            ValueError: If invoice not found
        """
        # Get invoice
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        period = self._get_open_period_for_active_invoice(invoice)
        vat_summaries = self._get_active_invoice_vat_summaries(invoice_id)
        return self._create_active_invoice_movements(invoice, period, vat_summaries)

    def create_from_passive_invoice(self, passive_invoice_id: UUID) -> list[VatMovement]:
        """
        Create VAT movements from a passive invoice.

        Args:
            passive_invoice_id: PassiveInvoice UUID

        Returns:
            List of created VatMovement instances

        Raises:
            ValueError: If passive invoice not found
        """
        # Get passive invoice
        passive_invoice = self.db.get(PassiveInvoice, passive_invoice_id)
        if not passive_invoice:
            raise ValueError(f"Passive invoice not found: {passive_invoice_id}")

        # Get VAT summaries
        query = select(PassiveInvoiceVatSummary).where(
            PassiveInvoiceVatSummary.passive_invoice_id == passive_invoice_id
        )
        vat_summaries = self.db.scalars(query).all()

        if not vat_summaries:
            logger.warning(f"No VAT summaries found for passive invoice {passive_invoice_id}")
            return []

        # Use vat_competence_date from passive invoice
        vat_competence_date = passive_invoice.vat_competence_date

        # Get or create period (assume QUARTERLY for now)
        period = self.period_service.get_or_create_period(
            passive_invoice.company_id,
            vat_competence_date,
            "QUARTERLY",
        )

        # Check if period is closed/settled
        if period.status in ("CLOSED", "SETTLED"):
            raise ValueError(
                f"Cannot create movements for passive invoice in {period.status} period. "
                f"Period: {period.year}-{period.frequency}-{period.period_index}"
            )

        # Create movements
        movements = []
        for summary in vat_summaries:
            movement = VatMovement(
                company_id=passive_invoice.company_id,
                period_id=period.id,
                source_type="PASSIVE_INVOICE",
                source_invoice_id=None,
                source_passive_invoice_id=passive_invoice_id,
                movement_type="CREDIT",
                document_date=passive_invoice.invoice_date,
                registration_date=passive_invoice.registration_date,
                vat_competence_date=vat_competence_date,
                vat_rate=summary.vat_rate,
                vat_nature=summary.vat_nature,
                taxable_amount=summary.taxable_amount,
                vat_amount=summary.vat_amount,
            )
            self.db.add(movement)
            movements.append(movement)

        self.db.flush()

        logger.info(
            f"Created {len(movements)} CREDIT VAT movements for passive invoice {passive_invoice_id} in period {period.id}"
        )

        return movements

    def replace_for_active_invoice(self, invoice_id: UUID) -> list[VatMovement]:
        """
        Replace VAT movements for an active invoice (delete old, create new).

        Args:
            invoice_id: Invoice UUID

        Returns:
            List of newly created VatMovement instances

        Raises:
            ValueError: If invoice not found or period is closed/settled
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")

        self._get_open_period_for_active_invoice(invoice)

        # Delete existing movements
        delete_query = delete(VatMovement).where(
            VatMovement.source_type == "ACTIVE_INVOICE",
            VatMovement.source_invoice_id == invoice_id,
        )
        result = self.db.execute(delete_query)
        deleted_count = result.rowcount

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing VAT movements for invoice {invoice_id}")

        # Create new movements
        return self.create_from_active_invoice(invoice_id)

    def replace_for_passive_invoice(self, passive_invoice_id: UUID) -> list[VatMovement]:
        """
        Replace VAT movements for a passive invoice (delete old, create new).

        Args:
            passive_invoice_id: PassiveInvoice UUID

        Returns:
            List of newly created VatMovement instances

        Raises:
            ValueError: If passive invoice not found or period is closed/settled
        """
        # Delete existing movements
        delete_query = delete(VatMovement).where(
            VatMovement.source_type == "PASSIVE_INVOICE",
            VatMovement.source_passive_invoice_id == passive_invoice_id,
        )
        result = self.db.execute(delete_query)
        deleted_count = result.rowcount

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing VAT movements for passive invoice {passive_invoice_id}")

        # Create new movements
        return self.create_from_passive_invoice(passive_invoice_id)

    def _get_open_period_for_active_invoice(self, invoice: Invoice) -> VatPeriod:
        period = self.period_service.get_or_create_period(
            invoice.company_id,
            invoice.issue_date,
            "QUARTERLY",
        )

        if period.status in ("CLOSED", "SETTLED"):
            raise ValueError(
                f"Cannot create movements for invoice in {period.status} period. "
                f"Period: {period.year}-{period.frequency}-{period.period_index}"
            )

        return period

    def _get_active_invoice_vat_summaries(self, invoice_id: UUID) -> list[InvoiceVatSummary]:
        query = select(InvoiceVatSummary).where(InvoiceVatSummary.invoice_id == invoice_id)
        vat_summaries = self.db.scalars(query).all()

        if not vat_summaries:
            logger.warning(f"No VAT summaries found for invoice {invoice_id}")
            return []

        return vat_summaries

    def _create_active_invoice_movements(
        self,
        invoice: Invoice,
        period: VatPeriod,
        vat_summaries: list[InvoiceVatSummary],
    ) -> list[VatMovement]:
        if self._is_split_payment_invoice(invoice):
            logger.info(
                "Skipping DEBIT VAT movements for split-payment invoice %s",
                invoice.id,
            )
            return []

        movements = []
        for summary in vat_summaries:
            movement = VatMovement(
                company_id=invoice.company_id,
                period_id=period.id,
                source_type="ACTIVE_INVOICE",
                source_invoice_id=invoice.id,
                source_passive_invoice_id=None,
                movement_type="DEBIT",
                document_date=invoice.issue_date,
                registration_date=invoice.issue_date,
                vat_competence_date=invoice.issue_date,
                vat_rate=summary.vat_rate,
                vat_nature=summary.vat_nature,
                taxable_amount=summary.taxable_amount,
                vat_amount=summary.vat_amount,
            )
            self.db.add(movement)
            movements.append(movement)

        self.db.flush()

        logger.info(
            "Created %s DEBIT VAT movements for active invoice %s in period %s",
            len(movements),
            invoice.id,
            period.id,
        )

        return movements

    @staticmethod
    def _is_split_payment_invoice(invoice: Invoice) -> bool:
        esigibilita = invoice.esigibilita_iva
        if esigibilita is None:
            return False
        if isinstance(esigibilita, EsigibilitaIVA):
            return esigibilita == EsigibilitaIVA.SPLIT
        if isinstance(esigibilita, str):
            return esigibilita in {EsigibilitaIVA.SPLIT.value, EsigibilitaIVA.SPLIT.name}
        return False
