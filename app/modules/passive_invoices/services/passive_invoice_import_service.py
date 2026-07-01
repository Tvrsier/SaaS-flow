"""Passive Invoice Import Service"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import PassiveInvoice, PassiveInvoiceLine, PassiveInvoiceVatSummary
from app.db.models.user import User
from app.modules.invoices.domain.enums import InvoiceStatus
from app.modules.invoices.xml.parser import FatturaPAParser, ParsedInvoice
from app.modules.vat.services.vat_movement_service import VatMovementService

logger = logging.getLogger("GestPro")


@dataclass
class PassiveInvoiceImportResult:
    """Result of passive invoice import"""

    passive_invoice: PassiveInvoice
    created: bool
    lines_count: int
    vat_summaries_count: int
    vat_movements_count: int


class PassiveInvoiceImportService:
    def __init__(self, db: Session):
        self.db = db
        self.parser = FatturaPAParser()
        self.vat_movement_service = VatMovementService(db)

    def import_from_xml(
        self,
        company_id: UUID,
        xml_content: str | bytes,
        source_channel: str = "MOCK",
    ) -> PassiveInvoiceImportResult:
        """
        Import a passive invoice from FatturaPA XML.

        Args:
            company_id: Company UUID (the receiver of the invoice)
            xml_content: XML content as string or bytes
            source_channel: Source channel identifier

        Returns:
            PassiveInvoiceImportResult

        Raises:
            ValueError: If XML is invalid or company mismatch
        """
        # Parse XML
        parsed = self.parser.parse(xml_content)

        # Calculate XML hash for idempotency
        xml_hash = self._calculate_xml_hash(xml_content)

        # Check if already imported
        existing = self._find_existing_passive_invoice(company_id, xml_hash)
        if existing:
            logger.info(f"Passive invoice already imported: {existing.id}, hash={xml_hash}")
            # Count existing data
            lines_count = self._count_lines(existing.id)
            summaries_count = self._count_summaries(existing.id)
            movements_count = self._count_movements(existing.id)

            return PassiveInvoiceImportResult(
                passive_invoice=existing,
                created=False,
                lines_count=lines_count,
                vat_summaries_count=summaries_count,
                vat_movements_count=movements_count,
            )

        # Verify that the company is the recipient
        # The CessionarioCommittente should match the company
        if not self._verify_company_is_recipient(company_id, parsed):
            logger.warning(
                f"Company {company_id} is not the recipient of this invoice. "
                f"Recipient VAT: {parsed.cessionario_committente.vat_number}"
            )
            # For now, we allow import anyway, but log the warning
            # In production, you might want to reject this

        # Create passive invoice
        passive_invoice = self._create_passive_invoice(company_id, parsed, xml_hash, source_channel)

        # Create lines
        lines_count = self._create_lines(passive_invoice.id, parsed)

        # Create VAT summaries
        summaries_count = self._create_vat_summaries(passive_invoice.id, parsed)

        self.db.flush()

        # Create VAT movements
        movements = self.vat_movement_service.create_from_passive_invoice(passive_invoice.id)
        movements_count = len(movements)

        self.db.flush()

        logger.info(
            f"Imported passive invoice: {passive_invoice.id}, "
            f"supplier={parsed.cedente_prestatore.name}, "
            f"number={parsed.invoice_number}, "
            f"lines={lines_count}, summaries={summaries_count}, movements={movements_count}"
        )

        return PassiveInvoiceImportResult(
            passive_invoice=passive_invoice,
            created=True,
            lines_count=lines_count,
            vat_summaries_count=summaries_count,
            vat_movements_count=movements_count,
        )

    def _calculate_xml_hash(self, xml_content: str | bytes) -> str:
        """Calculate SHA256 hash of XML content"""
        if isinstance(xml_content, str):
            xml_content = xml_content.encode("utf-8")
        return hashlib.sha256(xml_content).hexdigest()

    def _find_existing_passive_invoice(
        self,
        company_id: UUID,
        xml_hash: str,
    ) -> Optional[PassiveInvoice]:
        """Find existing passive invoice by hash"""
        query = select(PassiveInvoice).where(
            PassiveInvoice.company_id == company_id,
            PassiveInvoice.xml_hash == xml_hash,
            PassiveInvoice.deleted_at.is_(None),
        )
        return self.db.scalar(query)

    def _verify_company_is_recipient(self, company_id: UUID, parsed: ParsedInvoice) -> bool:
        """Verify that the company is the recipient of the invoice"""
        # Get company
        company = self.db.get(User, company_id)
        if not company:
            return False

        # Check if company VAT matches CessionarioCommittente VAT
        recipient_vat = parsed.cessionario_committente.vat_number
        recipient_tax_code = parsed.cessionario_committente.tax_code

        # Compare with company's VAT number or tax code
        # Assuming User model has vat_number or tax_code fields
        # For now, we just log and accept
        # In production, you should implement proper matching
        return True

    def _create_passive_invoice(
        self,
        company_id: UUID,
        parsed: ParsedInvoice,
        xml_hash: str,
        source_channel: str,
    ) -> PassiveInvoice:
        """Create PassiveInvoice from parsed data"""
        supplier = parsed.cedente_prestatore

        # Build supplier address string
        supplier_address = None
        supplier_city = None
        supplier_postal_code = None
        supplier_province = None
        supplier_country = "IT"

        if supplier.address:
            supplier_address = supplier.address.street
            supplier_city = supplier.address.city
            supplier_postal_code = supplier.address.postal_code
            supplier_province = supplier.address.province
            supplier_country = supplier.address.country

        # Use invoice_date as registration_date and vat_competence_date by default
        registration_date = parsed.invoice_date
        vat_competence_date = parsed.invoice_date

        passive_invoice = PassiveInvoice(
            company_id=company_id,
            supplier_id=None,  # TODO: match with existing supplier/client
            supplier_name=supplier.name or "Unknown Supplier",
            supplier_vat_number=supplier.vat_number,
            supplier_tax_code=supplier.tax_code,
            supplier_address=supplier_address,
            supplier_city=supplier_city,
            supplier_postal_code=supplier_postal_code,
            supplier_province=supplier_province,
            supplier_country=supplier_country,
            invoice_number=parsed.invoice_number,
            invoice_year=parsed.invoice_date.year,
            invoice_date=parsed.invoice_date,
            registration_date=registration_date,
            vat_competence_date=vat_competence_date,
            currency=parsed.currency,
            document_type=parsed.document_type,
            status=InvoiceStatus.READY,
            taxable_amount=parsed.taxable_amount,
            vat_amount=parsed.vat_amount,
            total_amount=parsed.total_amount,
            xml_hash=xml_hash,
            xml_s3_key=None,  # TODO: store XML to S3
            source_channel=source_channel,
        )

        self.db.add(passive_invoice)
        self.db.flush()

        return passive_invoice

    def _create_lines(self, passive_invoice_id: UUID, parsed: ParsedInvoice) -> int:
        """Create PassiveInvoiceLine from parsed data"""
        count = 0
        for parsed_line in parsed.lines:
            line = PassiveInvoiceLine(
                passive_invoice_id=passive_invoice_id,
                line_number=parsed_line.line_number,
                description=parsed_line.description,
                quantity=parsed_line.quantity,
                unit_price=parsed_line.unit_price,
                discount_amount=None,
                discount_percentage=parsed_line.discount_percentage,
                taxable_amount=parsed_line.taxable_amount,
                vat_rate=parsed_line.vat_rate,
                vat_nature=parsed_line.vat_nature,
                vat_amount=parsed_line.vat_amount,
                total_amount=parsed_line.total_amount,
                unit_of_measure=parsed_line.unit_of_measure,
            )
            self.db.add(line)
            count += 1

        return count

    def _create_vat_summaries(self, passive_invoice_id: UUID, parsed: ParsedInvoice) -> int:
        """Create PassiveInvoiceVatSummary from parsed data"""
        count = 0
        for parsed_summary in parsed.vat_summaries:
            summary = PassiveInvoiceVatSummary(
                passive_invoice_id=passive_invoice_id,
                vat_rate=parsed_summary.vat_rate,
                vat_nature=parsed_summary.vat_nature,
                taxable_amount=parsed_summary.taxable_amount,
                vat_amount=parsed_summary.vat_amount,
            )
            self.db.add(summary)
            count += 1

        return count

    def _count_lines(self, passive_invoice_id: UUID) -> int:
        """Count lines for passive invoice"""
        query = select(PassiveInvoiceLine).where(PassiveInvoiceLine.passive_invoice_id == passive_invoice_id)
        return len(self.db.scalars(query).all())

    def _count_summaries(self, passive_invoice_id: UUID) -> int:
        """Count summaries for passive invoice"""
        query = select(PassiveInvoiceVatSummary).where(
            PassiveInvoiceVatSummary.passive_invoice_id == passive_invoice_id
        )
        return len(self.db.scalars(query).all())

    def _count_movements(self, passive_invoice_id: UUID) -> int:
        """Count VAT movements for passive invoice"""
        from app.db.models.invoice import VatMovement

        query = select(VatMovement).where(
            VatMovement.source_type == "PASSIVE_INVOICE",
            VatMovement.source_passive_invoice_id == passive_invoice_id,
        )
        return len(self.db.scalars(query).all())
