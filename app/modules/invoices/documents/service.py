from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.invoice import Client, Invoice, InvoiceDocument, InvoiceLine, InvoicePayment, InvoicePaymentDetails, InvoiceVatSummary
from app.db.models.user import User, UserAddress
from app.modules.invoices.documents.dto import AddressDTO, InvoiceDocumentDTO, InvoiceLineDTO, PartyDTO, PaymentDetailsDTO, RelatedDocumentDTO, VatSummaryDTO
from app.modules.invoices.documents.exceptions import InvalidInvoiceNumberError, InvoiceDocumentGenerationError, InvoiceNotFoundError
from app.modules.invoices.documents.paths import get_invoice_pdf_path, get_invoice_xml_path
from app.modules.invoices.documents.pdf_generator import build_invoice_pdf
from app.modules.invoices.documents.repository import InvoiceRepository
from app.modules.invoices.documents.xml_generator import build_invoice_xml

DocumentType = Literal["pdf", "xml"]
logger = logging.getLogger("GestPro")
_document_locks: dict[tuple[UUID, DocumentType], asyncio.Lock] = {}


def _value(value: object | None, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


@dataclass(frozen=True, slots=True)
class GeneratedInvoiceDocuments:
    pdf_path: Path | None
    xml_path: Path | None


@dataclass(frozen=True, slots=True)
class InvoiceDownload:
    path: Path
    media_type: str
    download_name: str


class InvoiceDocumentService:
    def __init__(self, session: Session, root: Path | None = None):
        self.session = session
        self.root = root or get_settings().invoice_files_root
        self.repository = InvoiceRepository(session)

    async def generate_documents(
        self,
        *,
        invoice_id: UUID,
        document_types: set[DocumentType] | None = None,
        force: bool = False,
        origin: str = "download_regeneration",
    ) -> GeneratedInvoiceDocuments:
        requested_types = document_types or {"pdf", "xml"}
        if not requested_types.issubset({"pdf", "xml"}):
            raise InvoiceDocumentGenerationError("Unsupported document type")
        dto = self._build_dto(invoice_id)
        paths: dict[DocumentType, Path] = {
            "pdf": get_invoice_pdf_path(self.root, dto.invoice_id, dto.invoice_number),
            "xml": get_invoice_xml_path(self.root, dto.invoice_id, dto.invoice_number),
        }
        paths[next(iter(requested_types))].parent.mkdir(parents=True, exist_ok=True)

        for document_type in sorted(requested_types):
            lock = _document_locks.setdefault((invoice_id, document_type), asyncio.Lock())
            started = time.monotonic()
            async with lock:
                path = paths[document_type]
                if not force and self._is_usable(path):
                    logger.info("invoice_document reused invoice_id=%s type=%s origin=%s duration_ms=%d", invoice_id, document_type, origin, int((time.monotonic() - started) * 1000))
                    continue
                try:
                    content = build_invoice_pdf(dto) if document_type == "pdf" else build_invoice_xml(dto)
                    self._atomic_write(path, content)
                    logger.info("invoice_document generated invoice_id=%s type=%s origin=%s duration_ms=%d", invoice_id, document_type, origin, int((time.monotonic() - started) * 1000))
                except InvoiceDocumentGenerationError:
                    logger.exception("invoice_document failed invoice_id=%s type=%s origin=%s", invoice_id, document_type, origin)
                    raise
                except Exception as exc:
                    logger.exception("invoice_document failed invoice_id=%s type=%s origin=%s", invoice_id, document_type, origin)
                    raise InvoiceDocumentGenerationError("Document generation failed") from exc

        return GeneratedInvoiceDocuments(
            pdf_path=paths["pdf"] if "pdf" in requested_types else None,
            xml_path=paths["xml"] if "xml" in requested_types else None,
        )

    async def get_for_download(
        self,
        *,
        authenticated_company_id: UUID,
        invoice_number: str,
        document_type: DocumentType,
    ) -> InvoiceDownload:
        number = self._validate_invoice_number(invoice_number)
        invoice = self.repository.get_by_number_for_company(company_id=authenticated_company_id, invoice_number=number)
        if invoice is None:
            raise InvoiceNotFoundError()
        invoice_id = cast(UUID, invoice.id)
        path = get_invoice_pdf_path(self.root, invoice_id, number) if document_type == "pdf" else get_invoice_xml_path(self.root, invoice_id, number)
        if not self._is_usable(path):
            await self.generate_documents(invoice_id=invoice_id, document_types={document_type}, origin="download_regeneration")
        if not self._is_usable(path):
            raise InvoiceDocumentGenerationError("Generated document is unavailable")
        return InvoiceDownload(
            path=path,
            media_type="application/pdf" if document_type == "pdf" else "application/xml",
            download_name=f"{number}.{document_type}",
        )

    @staticmethod
    def _validate_invoice_number(value: str) -> str:
        value = value.strip()
        if not value or len(value) > 20 or any(ord(char) < 32 for char in value):
            raise InvalidInvoiceNumberError()
        return value

    @staticmethod
    def _is_usable(path: Path) -> bool:
        try:
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        if not content:
            raise InvoiceDocumentGenerationError("Empty document")
        temporary = path.with_suffix(f"{path.suffix}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.stat().st_size == 0:
                raise InvoiceDocumentGenerationError("Empty temporary document")
            os.replace(temporary, path)
        except InvoiceDocumentGenerationError:
            raise
        except OSError as exc:
            raise InvoiceDocumentGenerationError("Could not persist document") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _build_dto(self, invoice_id: UUID) -> InvoiceDocumentDTO:
        invoice = self.session.get(Invoice, invoice_id)
        if invoice is None or invoice.deleted_at is not None or not invoice.invoice_number:
            raise InvoiceNotFoundError()
        seller = self.session.get(User, invoice.company_id)
        client_id = invoice.customer_id or invoice.client_id
        customer = self.session.get(Client, client_id) if client_id else None
        if seller is None or customer is None:
            raise InvoiceDocumentGenerationError("Invoice parties are incomplete")
        seller_address = self.session.scalar(
            select(UserAddress).where(UserAddress.user_id == seller.id, UserAddress.deleted_at.is_(None)).order_by(UserAddress.created_at.asc())
        )
        lines = self.session.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id).order_by(InvoiceLine.line_number)).all()
        summaries = self.session.scalars(select(InvoiceVatSummary).where(InvoiceVatSummary.invoice_id == invoice_id).order_by(InvoiceVatSummary.vat_rate)).all()
        payment = self.session.scalar(select(InvoicePayment).where(InvoicePayment.invoice_id == invoice_id).order_by(InvoicePayment.created_at.asc()))
        details = self.session.get(InvoicePaymentDetails, invoice_id)
        documents = self.session.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice_id, InvoiceDocument.xml_block != "ALLEGATI")).all()

        seller_name = seller.company_name or " ".join(filter(None, [seller.first_name, seller.last_name])) or seller.email
        customer_name = customer.company_name or " ".join(filter(None, [customer.first_name, customer.last_name])) or customer.tax_code or "Cliente"
        payment_dto = None
        if payment:
            payment_dto = PaymentDetailsDTO(
                method=_value(payment.payment_method), due_date=payment.due_date, amount=payment.amount,
                beneficiary=details.beneficiary if details else None, financial_institution=details.financial_institution if details else None,
                iban=details.iban if details else payment.iban, abi=details.abi if details else None, cab=details.cab if details else None,
                bic=details.bic if details else None, payment_code=details.payment_code if details else None,
                postal_office_code=details.postal_office_code if details else None,
            )
        metadata = invoice.invoice_metadata or {}
        return InvoiceDocumentDTO(
            invoice_id=cast(UUID, invoice.id), invoice_number=invoice.invoice_number, issue_date=invoice.issue_date,
            document_type=_value(invoice.document_type), currency=invoice.currency,
            seller=PartyDTO(
                name=seller_name, first_name=seller.first_name, last_name=seller.last_name,
                vat_number=seller.partita_iva, tax_code=seller.codice_fiscale, email=seller.email,
                address=AddressDTO(
                    street=seller_address.address if seller_address else "N/D", street_number=seller_address.street_number if seller_address else None,
                    postal_code=seller_address.postal_code if seller_address else None, city=seller_address.city if seller_address else None,
                    province=seller_address.province if seller_address else None, country=seller_address.country if seller_address else "IT",
                ),
            ),
            customer=PartyDTO(
                name=customer_name, first_name=customer.first_name, last_name=customer.last_name,
                vat_number=customer.vat_number, tax_code=customer.tax_code, recipient_code=customer.recipient_code, pec=customer.pec,
                address=AddressDTO(street=customer.address, street_number=None, postal_code=customer.postal_code, city=customer.city, province=customer.province, country=customer.country),
            ),
            lines=tuple(InvoiceLineDTO(number=line.line_number, description=line.description, quantity=line.quantity, unit_of_measure=line.unit_of_measure, unit_price=line.unit_price, taxable_amount=line.taxable_amount, vat_rate=line.vat_rate, vat_nature=_value(line.vat_nature) or None, vat_amount=line.vat_amount, total_amount=line.total_amount) for line in lines),
            vat_summaries=tuple(VatSummaryDTO(vat_rate=item.vat_rate, vat_nature=_value(item.vat_nature) or None, taxable_amount=item.taxable_amount, vat_amount=item.vat_amount) for item in summaries),
            payment_details=payment_dto,
            related_documents=tuple(RelatedDocumentDTO(document_type=item.xml_block, document_number=item.document_number, document_date=item.document_date, line_numbers=tuple(item.reference_line_numbers or []), metadata=tuple(sorted((item.document_metadata or {}).items()))) for item in documents),
            ddt=tuple(cast(list[dict[str, object]], metadata.get("ddt", []))),
            taxable_amount=invoice.taxable_amount, vat_amount=invoice.vat_amount, total_amount=invoice.total_amount,
            vat_collectability=_value(invoice.esigibilita_iva, "I") or "I",
        )
