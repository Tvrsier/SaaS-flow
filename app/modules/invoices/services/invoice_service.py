from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.invoice import Client, Invoice, InvoiceAttachment, InvoiceLine, InvoiceVatSummary
from app.db.models.user import User
from app.modules.invoices.domain.enums import ClientType, InvoiceStatus, NatureCode
from app.modules.invoices.schemas.api import InvoiceAttachmentPayload, InvoiceClientPayload, InvoiceCreateRequest, InvoiceLinePayload

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass(slots=True, frozen=True)
class InvoiceCalculation:
    subtotal: Decimal
    vat_total: Decimal
    total: Decimal
    vat_groups: list[tuple[Decimal, NatureCode | None, Decimal, Decimal]]


class InvoiceService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def create_invoice(self, current_user: User, payload: InvoiceCreateRequest) -> dict[str, object]:
        self._ensure_user_can_issue(current_user)
        calc = self._calculate(payload)
        self._validate_calculated_totals(payload, calc)

        written_files: list[Path] = []
        try:
            client = self._create_client(current_user, payload.client)
            self.db.add(client)
            self.db.flush()

            invoice = Invoice(
                company_id=current_user.id,
                customer_id=None,
                client_id=client.id,
                invoice_number=payload.invoice_number,
                invoice_year=payload.issue_date.year,
                invoice_section="",
                document_type=payload.document_type,
                status=InvoiceStatus.DRAFT if payload.mode == 1 else InvoiceStatus.READY,
                issue_date=payload.issue_date,
                due_date=None,
                currency=payload.currency.value,
                notes=None,
                taxable_amount=calc.subtotal,
                vat_amount=calc.vat_total,
                total_amount=calc.total,
                withholding_amount=ZERO,
                stamp_duty_amount=ZERO,
                rounding_amount=ZERO,
                supplier_name=self._supplier_name(current_user),
                supplier_vat_number=self._supplier_vat_number(current_user),
                supplier_tax_code=self._supplier_tax_code(current_user),
                supplier_address=self._supplier_address(),
                supplier_city=self._supplier_city(),
                supplier_postal_code=self._supplier_postal_code(),
                supplier_province=self._supplier_province(),
                supplier_country=self._supplier_country(),
            )
            self.db.add(invoice)
            self.db.flush()

            lines = [self._create_line(invoice.id, line) for line in payload.lines]
            self.db.add_all(lines)

            vat_summaries = [
                InvoiceVatSummary(
                    invoice_id=invoice.id,
                    vat_rate=vat_rate,
                    vat_nature=nature,
                    taxable_amount=taxable_amount,
                    vat_amount=vat_amount,
                )
                for vat_rate, nature, taxable_amount, vat_amount in calc.vat_groups
            ]
            self.db.add_all(vat_summaries)

            attachments = self._create_attachments(invoice.id, payload.attachments, written_files)
            self.db.add_all(attachments)

            self.db.commit()
            self.db.refresh(invoice)
            self.db.refresh(client)
            for line in lines:
                self.db.refresh(line)
            for summary in vat_summaries:
                self.db.refresh(summary)
            for attachment in attachments:
                self.db.refresh(attachment)

            return self._serialize_invoice(invoice, client, lines, vat_summaries, attachments)
        except HTTPException:
            self.db.rollback()
            self._cleanup_files(written_files)
            raise
        except (ValueError, UnicodeDecodeError, OSError, TypeError) as exc:
            self.db.rollback()
            self._cleanup_files(written_files)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": str(exc)}) from exc

    def list_invoices(self, current_user: User, page: int | None = None, per_page: int | None = None) -> dict[str, object]:
        self._ensure_user_can_issue(current_user)
        query = (
            select(Invoice)
            .where(Invoice.company_id == current_user.id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
        )

        total = self.db.scalar(select(func.count()).select_from(Invoice).where(Invoice.company_id == current_user.id, Invoice.deleted_at.is_(None))) or 0

        if page is not None and per_page is not None:
            query = query.offset((page - 1) * per_page).limit(per_page)

        invoices = self.db.scalars(query).all()
        last_invoice_number = self.db.scalar(
            select(Invoice.invoice_number)
            .where(Invoice.company_id == current_user.id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
            .limit(1)
        )

        data: list[dict[str, object]] = []
        for invoice in invoices:
            client = self.db.get(Client, invoice.client_id) if invoice.client_id else None
            lines = self.db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id).order_by(InvoiceLine.line_number.asc())).all()
            summaries = self.db.scalars(select(InvoiceVatSummary).where(InvoiceVatSummary.invoice_id == invoice.id).order_by(InvoiceVatSummary.vat_rate.asc())).all()
            attachments = self.db.scalars(select(InvoiceAttachment).where(InvoiceAttachment.invoice_id == invoice.id).order_by(InvoiceAttachment.created_at.asc())).all()
            if client is None:
                continue
            data.append(self._serialize_invoice(invoice, client, lines, summaries, attachments))

        return {
            "data": data,
            "lastInvoiceNumber": last_invoice_number,
            "page": page,
            "perPage": per_page,
            "total": int(total),
            "count": len(data),
        }

    def _ensure_user_can_issue(self, current_user: User) -> None:
        if not current_user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not active")

    def _calculate(self, payload: InvoiceCreateRequest) -> InvoiceCalculation:
        vat_groups: dict[tuple[Decimal, NatureCode | None], dict[str, Decimal]] = {}
        subtotal = ZERO
        vat_total = ZERO

        for line in payload.lines:
            taxable_amount = line.line_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            vat_amount = (taxable_amount * line.vat_rate / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            subtotal += taxable_amount
            vat_total += vat_amount
            group_key = (line.vat_rate, line.nature)
            group = vat_groups.setdefault(group_key, {"taxable": ZERO, "vat": ZERO})
            group["taxable"] = (group["taxable"] + taxable_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            group["vat"] = (group["vat"] + vat_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        subtotal = subtotal.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        vat_total = vat_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total = (subtotal + vat_total).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        vat_groups_sorted = [
            (vat_rate, nature, values["taxable"], values["vat"])
            for (vat_rate, nature), values in sorted(
                vat_groups.items(),
                key=lambda item: (item[0][0], item[0][1].value if item[0][1] is not None else ""),
            )
        ]
        return InvoiceCalculation(subtotal=subtotal, vat_total=vat_total, total=total, vat_groups=vat_groups_sorted)

    def _validate_calculated_totals(self, payload: InvoiceCreateRequest, calc: InvoiceCalculation) -> None:
        if payload.subtotal.quantize(TWOPLACES, rounding=ROUND_HALF_UP) != calc.subtotal:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": "subtotal does not match invoice lines"})
        if payload.vat_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP) != calc.vat_total:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": "vatTotal does not match invoice lines"})
        if payload.total.quantize(TWOPLACES, rounding=ROUND_HALF_UP) != calc.total:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": "total does not match invoice lines"})

    def _create_client(self, current_user: User, payload: InvoiceClientPayload) -> Client:
        client_type = {
            "private": ClientType.PRIVATE,
            "company": ClientType.COMPANY,
            "public_administration": ClientType.PUBLIC_ADMINISTRATION,
        }[payload.client_type.value]

        return Client(
            company_id=current_user.id,
            client_type=client_type,
            first_name=payload.first_name,
            last_name=payload.last_name,
            company_name=payload.company_name,
            vat_number=payload.vat_number,
            tax_code=payload.tax_code,
            address=payload.address,
            city=payload.city,
            postal_code=payload.postal_code,
            province=payload.province,
            country=payload.country,
            pec=payload.pec,
            recipient_code=payload.recipient_code or "0000000",
        )

    def _create_line(self, invoice_id: UUID, payload: InvoiceLinePayload) -> InvoiceLine:
        vat_amount = (payload.line_total * payload.vat_rate / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        return InvoiceLine(
            invoice_id=invoice_id,
            line_number=payload.number_line,
            description=payload.description,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            discount_amount=None,
            discount_percentage=None,
            taxable_amount=payload.line_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            vat_rate=payload.vat_rate,
            vat_nature=payload.nature,
            vat_amount=vat_amount,
            total_amount=(payload.line_total + vat_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            product_id=None,
            unit_of_measure=payload.unit_measure,
        )

    def _create_attachments(
        self,
        invoice_id: UUID,
        attachments: list[InvoiceAttachmentPayload],
        written_files: list[Path],
    ) -> list[InvoiceAttachment]:
        if not attachments:
            return []

        base_dir = Path(self.settings.public_data_dir) / "invoices" / str(invoice_id) / "attachments"
        base_dir.mkdir(parents=True, exist_ok=True)

        created: list[InvoiceAttachment] = []
        for attachment in attachments:
            decoded = base64.b64decode(attachment.content_base64, validate=True)
            if len(decoded) != attachment.size:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"message": f"Attachment size mismatch for {attachment.file_name}"},
                )

            safe_name = self._safe_filename(attachment.file_name)
            attachment_id = uuid4()
            relative_key = f"invoices/{invoice_id}/attachments/{attachment_id}/{safe_name}"
            file_path = Path(self.settings.public_data_dir) / relative_key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(decoded)
            written_files.append(file_path)

            created.append(
                InvoiceAttachment(
                    id=attachment_id,
                    invoice_id=invoice_id,
                    filename=attachment.file_name,
                    mime_type=attachment.mime_type,
                    file_format=self._file_format(attachment.file_name, attachment.mime_type),
                    size_bytes=len(decoded),
                    s3_key=relative_key,
                    hash=hashlib.sha256(decoded).hexdigest(),
                    description=None,
                    included_in_xml=False,
                )
            )
        return created

    @staticmethod
    def _safe_filename(filename: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)

    @staticmethod
    def _file_format(filename: str, mime_type: str) -> str:
        suffix = Path(filename).suffix.lstrip(".")
        if suffix:
            return suffix.lower()
        if "/" in mime_type:
            return mime_type.split("/", 1)[1].lower()
        return mime_type.lower()

    @staticmethod
    def _cleanup_files(paths: list[Path]) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue

    def _supplier_name(self, current_user: User) -> str:
        if current_user.company_name:
            return current_user.company_name
        full_name = " ".join(part for part in [current_user.first_name, current_user.last_name] if part)
        return full_name or current_user.email

    def _supplier_vat_number(self, current_user: User) -> str:
        return current_user.partita_iva or current_user.codice_fiscale or ""

    def _supplier_tax_code(self, current_user: User) -> str | None:
        return current_user.codice_fiscale or current_user.partita_iva

    @staticmethod
    def _supplier_address() -> str:
        return ""

    @staticmethod
    def _supplier_city() -> str:
        return ""

    @staticmethod
    def _supplier_postal_code() -> str:
        return ""

    @staticmethod
    def _supplier_province() -> str | None:
        return None

    @staticmethod
    def _supplier_country() -> str:
        return "IT"

    def _serialize_invoice(
        self,
        invoice: Invoice,
        client: Client,
        lines: list[InvoiceLine],
        vat_summaries: list[InvoiceVatSummary],
        attachments: list[InvoiceAttachment],
    ) -> dict[str, object]:
        return {
            "id": str(invoice.id),
            "companyId": str(invoice.company_id),
            "clientId": str(invoice.client_id) if invoice.client_id else None,
            "invoiceNumber": invoice.invoice_number,
            "invoiceYear": invoice.invoice_year,
            "invoiceSection": invoice.invoice_section or None,
            "documentType": invoice.document_type,
            "status": invoice.status.value if isinstance(invoice.status, InvoiceStatus) else str(invoice.status),
            "issueDate": invoice.issue_date,
            "dueDate": invoice.due_date,
            "currency": invoice.currency,
            "notes": invoice.notes,
            "taxableAmount": invoice.taxable_amount,
            "vatAmount": invoice.vat_amount,
            "totalAmount": invoice.total_amount,
            "withholdingAmount": invoice.withholding_amount,
            "stampDutyAmount": invoice.stamp_duty_amount,
            "roundingAmount": invoice.rounding_amount,
            "client": {
                "id": str(client.id),
                "clientType": {
                    ClientType.PRIVATE: "private",
                    ClientType.COMPANY: "company",
                    ClientType.PUBLIC_ADMINISTRATION: "public_administration",
                }[client.client_type],
                "firstName": client.first_name,
                "lastName": client.last_name,
                "companyName": client.company_name,
                "vatNumber": client.vat_number,
                "taxCode": client.tax_code,
                "clientCode": client.vat_number or client.tax_code,
                "address": client.address,
                "city": client.city,
                "postalCode": client.postal_code,
                "province": client.province,
                "country": client.country,
                "pec": client.pec,
                "recipientCode": client.recipient_code,
            },
            "lines": [
                {
                    "id": str(line.id),
                    "numberLine": line.line_number,
                    "description": line.description,
                    "quantity": line.quantity,
                    "unitMeasure": line.unit_of_measure,
                    "unitPrice": line.unit_price,
                    "lineTotal": line.taxable_amount,
                    "vatRate": line.vat_rate,
                    "nature": line.vat_nature,
                }
                for line in lines
            ],
            "vatSummary": [
                {
                    "vatRate": summary.vat_rate,
                    "nature": summary.vat_nature,
                    "taxableAmount": summary.taxable_amount,
                    "vatAmount": summary.vat_amount,
                }
                for summary in vat_summaries
            ],
            "attachments": [
                {
                    "id": str(attachment.id),
                    "fileName": attachment.filename,
                    "mimeType": attachment.mime_type,
                    "fileFormat": attachment.file_format,
                    "size": attachment.size_bytes,
                    "s3Key": attachment.s3_key,
                    "hash": attachment.hash,
                    "includedInXml": attachment.included_in_xml,
                    "description": attachment.description,
                }
                for attachment in attachments
            ],
            "createdAt": invoice.created_at,
            "updatedAt": invoice.updated_at,
            "issuedAt": invoice.issued_at,
        }

