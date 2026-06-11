from __future__ import annotations

import base64
import logging
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID, uuid4
from typing import Optional, cast

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models.invoice import Client, Invoice, InvoiceDocument, InvoiceLine, InvoicePayment, InvoiceVatSummary
from app.db.models.user import User
from app.modules.invoices.domain.enums import ClientType, InvoiceStatus, NatureCode, PaymentMethod, PaymentStatus
from app.modules.invoices.schemas.api import ClientRead, ClientsListResponse, InvoiceAttachmentPayload, InvoiceClientPayload, InvoiceClientType, InvoiceCreateRequest, InvoiceDocumentPayload, InvoiceLinePayload, InvoiceRead, InvoicesListResponse

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")
DEFAULT_INVOICE_LIST_LIMIT = 20
logger = logging.getLogger("GestPro")


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

    def list_clients(self, current_user: User, q: str | None = None) -> ClientsListResponse:
        self._ensure_user_can_issue(current_user)
        query = select(Client).where(Client.company_id == current_user.id, Client.deleted_at.is_(None)).order_by(Client.created_at.asc(), Client.company_name.asc())

        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(
                or_(
                    Client.first_name.ilike(pattern),
                    Client.last_name.ilike(pattern),
                    Client.company_name.ilike(pattern),
                    Client.vat_number.ilike(pattern),
                    Client.tax_code.ilike(pattern),
                    Client.address.ilike(pattern),
                    Client.city.ilike(pattern),
                )
            )

        clients = self.db.scalars(query).all()
        data = [self._serialize_client(client) for client in clients]
        logger.debug(
            "list_clients resolved company_id=%s q=%r count=%d",
            current_user.id,
            q,
            len(data),
        )
        return ClientsListResponse(data=data)

    def create_invoice(
        self,
        current_user: User,
        payload: InvoiceCreateRequest,
        invoice_form_test: str | None = None,
    ) -> InvoiceRead:
        self._ensure_user_can_issue(current_user)
        calc = self._calculate(payload)
        self._validate_calculated_totals(payload, calc)

        test_mode = self._is_test_mode(invoice_form_test)
        now = datetime.now(timezone.utc) if test_mode else None
        written_files: list[Path] = []
        try:
            client = self._resolve_or_create_client(current_user, payload.client, test_mode=test_mode)
            test_invoice_id = uuid4() if test_mode else None

            invoice_metadata = self._build_invoice_metadata(payload)
            invoice = Invoice(
                company_id=current_user.id,
                customer_id=client.id,
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
                invoice_metadata=invoice_metadata,
            )
            if test_mode:
                invoice.id = cast(UUID, test_invoice_id)
                invoice.created_at = now
                invoice.updated_at = now
            else:
                self.db.add(invoice)
                self.db.flush()

            invoice_uuid = cast(UUID, cast(object, invoice.id))
            lines = [self._create_line(invoice_uuid, line) for line in payload.lines]
            vat_summaries = [
                InvoiceVatSummary(
                    invoice_id=invoice_uuid,
                    vat_rate=vat_rate,
                    vat_nature=nature,
                    taxable_amount=taxable_amount,
                    vat_amount=vat_amount,
                )
                for vat_rate, nature, taxable_amount, vat_amount in calc.vat_groups
            ]
            payments = [self._create_payment(invoice_uuid, payload.payment_method, calc.total, payload.issue_date)]
            related_document_fingerprints = {
                self._attachment_fingerprint(document.file)
                for document in payload.documents
                if document.related_document_type is not None and document.file is not None
            }

            attachment_payloads: list[InvoiceAttachmentPayload] = []
            attachment_fingerprints: set[tuple[str, str, str, int]] = set()
            for attachment in payload.attachments:
                fingerprint = self._attachment_fingerprint(attachment)
                if fingerprint in related_document_fingerprints or fingerprint in attachment_fingerprints:
                    continue
                attachment_payloads.append(attachment)
                attachment_fingerprints.add(fingerprint)

            document_payloads: list[InvoiceDocumentPayload] = []
            for document in payload.documents:
                if document.related_document_type is None and document.file is not None:
                    fingerprint = self._attachment_fingerprint(document.file)
                    if fingerprint in related_document_fingerprints or fingerprint in attachment_fingerprints:
                        continue
                    attachment_payloads.append(document.file)
                    attachment_fingerprints.add(fingerprint)
                    continue
                if document.related_document_type is not None:
                    document_payloads.append(document)

            attachments = self._create_attachments(invoice_uuid, attachment_payloads, written_files)
            documents = self._create_documents(invoice_uuid, document_payloads, written_files)

            if not test_mode:
                self.db.add_all(lines)
                self.db.add_all(vat_summaries)
                self.db.add_all(payments)
                self.db.add_all(attachments)
                self.db.add_all(documents)
                self.db.commit()
                self.db.refresh(invoice)
                self.db.refresh(client)
                for line in lines:
                    self.db.refresh(line)
                for summary in vat_summaries:
                    self.db.refresh(summary)
                for payment in payments:
                    self.db.refresh(payment)
                for attachment in attachments:
                    self.db.refresh(attachment)
                for document in documents:
                    self.db.refresh(document)
            else:
                self._cleanup_files(written_files)

            return InvoiceRead.model_validate(self._serialize_invoice(invoice, client, lines, vat_summaries, attachments, documents))
        except HTTPException:
            self.db.rollback()
            self._cleanup_files(written_files)
            raise
        except (ValueError, UnicodeDecodeError, OSError, TypeError) as exc:
            self.db.rollback()
            self._cleanup_files(written_files)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": str(exc)}) from exc

    def list_invoices(self, current_user: User, page: int | None = None, per_page: int | None = None) -> InvoicesListResponse:
        self._ensure_user_can_issue(current_user)
        page = page or 1
        per_page = per_page or DEFAULT_INVOICE_LIST_LIMIT
        query = (
            select(Invoice)
            .where(Invoice.company_id == current_user.id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
        )

        total = self.db.scalar(select(func.count()).select_from(Invoice).where(Invoice.company_id == current_user.id, Invoice.deleted_at.is_(None))) or 0

        query = query.offset((page - 1) * per_page).limit(per_page)

        invoices = self.db.scalars(query).all()
        last_invoice_number = self._get_last_invoice_number(current_user.id)

        data: list[dict[str, object]] = []
        for invoice in invoices:
            client_ref = invoice.customer_id or invoice.client_id
            client = cast(Optional[Client], self.db.get(Client, client_ref) if client_ref else None)
            lines = list(self.db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id).order_by(InvoiceLine.line_number.asc())).all())
            summaries = list(self.db.scalars(select(InvoiceVatSummary).where(InvoiceVatSummary.invoice_id == invoice.id).order_by(InvoiceVatSummary.vat_rate.asc())).all())
            attachments = list(self.db.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice.id, InvoiceDocument.xml_block == "ALLEGATI").order_by(InvoiceDocument.created_at.asc())).all())
            documents = list(self.db.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice.id, InvoiceDocument.xml_block != "ALLEGATI").order_by(InvoiceDocument.created_at.asc())).all())
            if client is None:
                continue
            data.append(self._serialize_invoice(invoice, client, lines, summaries, attachments, documents))

        return InvoicesListResponse.model_validate({
            "data": data,
            "lastInvoiceNumber": last_invoice_number,
            "page": page,
            "perPage": per_page,
            "total": int(total),
            "count": len(data),
        })

    def _get_last_invoice_number(self, company_id: UUID) -> str | None:
        latest_year = self.db.scalar(
            select(func.max(Invoice.invoice_year)).where(Invoice.company_id == company_id, Invoice.deleted_at.is_(None))
        )
        if latest_year is None:
            return None

        invoices = list(
            self.db.scalars(
                select(Invoice).where(
                    Invoice.company_id == company_id,
                    Invoice.deleted_at.is_(None),
                    Invoice.invoice_year == latest_year,
                    Invoice.invoice_number.is_not(None),
                )
            ).all()
        )
        if not invoices:
            return None

        return max(invoices, key=self._invoice_recency_key).invoice_number

    @staticmethod
    def _invoice_recency_key(invoice: Invoice) -> tuple[datetime, int, str]:
        created_at = invoice.created_at or datetime.min.replace(tzinfo=timezone.utc)
        invoice_number = (invoice.invoice_number or "").strip()
        match = re.search(r"(\d+)$", invoice_number)
        suffix = int(match.group(1)) if match else -1
        return created_at, suffix, invoice_number

    def _is_test_mode(self, invoice_form_test: str | None) -> bool:
        return isinstance(invoice_form_test, str) and invoice_form_test.lower() == "true"

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

    @staticmethod
    def _build_invoice_metadata(payload: InvoiceCreateRequest) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if payload.ddt:
            metadata["ddt"] = [
                {
                    "numero": ddt.numero_ddt,
                    "data": ddt.data_ddt.isoformat(),
                    "riferimento_linee": ddt.riferimento_numero_linea,
                }
                for ddt in payload.ddt
            ]
        return metadata

    def _resolve_or_create_client(self, current_user: User, payload: InvoiceClientPayload, test_mode: bool) -> Client:
        existing = self._find_existing_client(current_user, payload)
        if existing is not None:
            return existing

        client = self._create_client(current_user, payload)
        if test_mode:
            now = datetime.now(timezone.utc)
            client.id = uuid4()
            client.created_at = now
            client.updated_at = now
            return client

        self.db.add(client)
        self.db.flush()
        return client

    def _find_existing_client(self, current_user: User, payload: InvoiceClientPayload) -> Client | None:
        client_type = self._client_type_from_payload(payload)
        lookup_clauses = {
            ClientType.PRIVATE: [Client.tax_code == self._normalize_text(payload.tax_code, upper=True)],
            ClientType.COMPANY: [Client.vat_number == self._normalize_text(payload.vat_number, upper=True)],
            ClientType.PUBLIC_ADMINISTRATION: [
                Client.tax_code == self._normalize_text(payload.tax_code, upper=True),
                Client.recipient_code == self._normalize_text(payload.recipient_code or "0000000", upper=True),
            ],
        }[client_type]

        query = select(Client).where(
            Client.company_id == current_user.id,
            Client.deleted_at.is_(None),
            Client.client_type == client_type,
            *lookup_clauses,
        )

        client = self.db.scalars(query).first()
        if client is not None and self._client_matches_payload(client, payload):
            return client

        candidates = self.db.scalars(
            select(Client).where(
                Client.company_id == current_user.id,
                Client.deleted_at.is_(None),
                Client.client_type == client_type,
            )
        ).all()

        for client in candidates:
            if self._client_matches_payload(client, payload):
                return client
        return None

    def _client_matches_payload(self, client: Client, payload: InvoiceClientPayload) -> bool:
        if client.client_type != self._client_type_from_payload(payload):
            return False

        checks: list[tuple[str | None, str | None, bool]] = []
        if payload.first_name:
            checks.append((client.first_name, payload.first_name, False))
        if payload.last_name:
            checks.append((client.last_name, payload.last_name, False))
        if payload.company_name:
            checks.append((client.company_name, payload.company_name, False))
        if payload.vat_number:
            checks.append((client.vat_number, payload.vat_number, True))
        if payload.tax_code:
            checks.append((client.tax_code, payload.tax_code, True))
        if payload.address:
            checks.append((client.address, payload.address, False))
        if payload.city:
            checks.append((client.city, payload.city, False))
        if payload.postal_code:
            checks.append((client.postal_code, payload.postal_code, False))
        if payload.province:
            checks.append((client.province, payload.province, False))
        if payload.country:
            checks.append((client.country, payload.country, True))
        if payload.pec:
            checks.append((client.pec, payload.pec, False))
        if payload.recipient_code:
            checks.append((client.recipient_code, payload.recipient_code, True))

        return all(
            self._normalize_text(stored, upper=upper) == self._normalize_text(incoming, upper=upper)
            for stored, incoming, upper in checks
        )

    @staticmethod
    def _normalize_text(value: str | None, *, upper: bool = False) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned.upper() if upper else cleaned

    @staticmethod
    def _client_type_from_payload(payload: InvoiceClientPayload) -> ClientType:
        return {
            "private": ClientType.PRIVATE,
            "company": ClientType.COMPANY,
            "public_administration": ClientType.PUBLIC_ADMINISTRATION,
        }[payload.client_type.value]

    def _create_client(self, current_user: User, payload: InvoiceClientPayload) -> Client:
        return Client(
            company_id=current_user.id,
            client_type=self._client_type_from_payload(payload),
            first_name=payload.first_name or None,
            last_name=payload.last_name or None,
            company_name=payload.company_name or None,
            vat_number=payload.vat_number or None,
            tax_code=payload.tax_code or None,
            address=payload.address,
            city=payload.city or None,
            postal_code=payload.postal_code or None,
            province=payload.province or None,
            country=payload.country,
            pec=payload.pec or None,
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

    def _create_payment(self, invoice_id: UUID, payment_method: PaymentMethod, amount: Decimal, due_date) -> InvoicePayment:
        return InvoicePayment(
            invoice_id=invoice_id,
            payment_method=payment_method,
            payment_status=PaymentStatus.PENDING,
            due_date=due_date,
            amount=amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            paid_amount=ZERO,
            paid_at=None,
            iban=None,
            reference=None,
        )

    def _create_attachments(
        self,
        invoice_id: UUID,
        attachments: list[InvoiceAttachmentPayload],
        written_files: list[Path],
    ) -> list[InvoiceDocument]:
        if not attachments:
            return []

        base_dir = Path(self.settings.public_data_dir) / "invoices" / str(invoice_id) / "attachments"
        base_dir.mkdir(parents=True, exist_ok=True)

        created: list[InvoiceDocument] = []
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
                InvoiceDocument(
                    id=attachment_id,
                    invoice_id=invoice_id,
                    xml_block="ALLEGATI",
                    filename=attachment.file_name,
                    mime_type=attachment.mime_type,
                    file_format=self._file_format(attachment.file_name, attachment.mime_type),
                    size_bytes=len(decoded),
                    s3_key=relative_key,
                    hash=hashlib.sha256(decoded).hexdigest(),
                    document_number=None,
                    document_date=None,
                    reference_line_numbers=[],
                    document_metadata={},
                    description=attachment.description,
                    include_in_xml=False,
                )
            )
        return created

    def _create_documents(
        self,
        invoice_id: UUID,
        documents: list[InvoiceDocumentPayload],
        written_files: list[Path],
    ) -> list[InvoiceDocument]:
        if not documents:
            return []

        created: list[InvoiceDocument] = []
        for document in documents:
            file_payload = document.file
            if file_payload is not None:
                decoded = base64.b64decode(file_payload.content_base64, validate=True)
                if len(decoded) != file_payload.size:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"message": f"Attachment size mismatch for {file_payload.file_name}"},
                    )

                safe_name = self._safe_filename(file_payload.file_name)
                file_id = uuid4()
                relative_key = f"invoices/{invoice_id}/documents/{file_id}/{safe_name}"
                file_path = Path(self.settings.public_data_dir) / relative_key
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(decoded)
                written_files.append(file_path)

                filename = file_payload.file_name
                mime_type = file_payload.mime_type
                file_format = self._file_format(file_payload.file_name, file_payload.mime_type)
                size_bytes = len(decoded)
                s3_key = relative_key
                file_hash = hashlib.sha256(decoded).hexdigest()
                description = file_payload.description
            else:
                filename = None
                mime_type = None
                file_format = None
                size_bytes = None
                s3_key = None
                file_hash = None
                description = None

            metadata: dict[str, object] = {
                "numItem": document.num_item,
                "codiceCommessaConvenzione": document.codice_commessa_convenzione,
                "codiceCUP": document.codice_cup,
                "codiceCIG": document.codice_cig,
            }
            metadata = {key: value for key, value in metadata.items() if value is not None}

            created.append(
                InvoiceDocument(
                    id=uuid4(),
                    invoice_id=invoice_id,
                    xml_block=(document.related_document_type.value if document.related_document_type else "ALLEGATI"),
                    filename=filename,
                    mime_type=mime_type,
                    file_format=file_format,
                    size_bytes=size_bytes,
                    s3_key=s3_key,
                    hash=file_hash,
                    document_number=document.id_documento,
                    document_date=document.data,
                    reference_line_numbers=document.riferimento_numero_linea,
                    document_metadata=metadata,
                    description=description,
                    include_in_xml=True,
                )
            )
        return created

    @staticmethod
    def _safe_filename(filename: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)

    @staticmethod
    def _attachment_fingerprint(attachment: InvoiceAttachmentPayload) -> tuple[str, str, str, int]:
        return attachment.file_name, attachment.mime_type, attachment.content_base64, attachment.size

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

    def _serialize_invoice(
        self,
        invoice: Invoice,
        client: Client,
        lines: list[InvoiceLine],
        vat_summaries: list[InvoiceVatSummary],
        attachments: list[InvoiceDocument],
        documents: list[InvoiceDocument],
    ) -> dict[str, object]:
        return {
            "id": str(invoice.id),
            "companyId": str(invoice.company_id),
            "clientId": str(invoice.customer_id or invoice.client_id) if (invoice.customer_id or invoice.client_id) else None,
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
                    "includedInXml": attachment.include_in_xml,
                    "description": attachment.description,
                }
                for attachment in attachments
            ],
            "documents": [
                {
                    "id": str(document.id),
                    "file": (
                        {
                            "id": str(document.id),
                            "fileName": document.filename,
                            "mimeType": document.mime_type,
                            "fileFormat": document.file_format,
                            "size": document.size_bytes,
                            "s3Key": document.s3_key,
                            "hash": document.hash,
                            "includedInXml": document.include_in_xml,
                            "description": document.description,
                        }
                        if document.filename or document.mime_type or document.s3_key or document.hash
                        else None
                    ),
                    "relatedDocumentType": document.xml_block if document.xml_block != "ALLEGATI" else None,
                    "idDocumento": document.document_number,
                    "riferimentoNumeroLinea": document.reference_line_numbers or [],
                    "data": document.document_date,
                    "numItem": (document.document_metadata or {}).get("numItem"),
                    "codiceCommessaConvenzione": (document.document_metadata or {}).get("codiceCommessaConvenzione"),
                    "codiceCUP": (document.document_metadata or {}).get("codiceCUP"),
                    "codiceCIG": (document.document_metadata or {}).get("codiceCIG"),
                    "includedInXml": document.include_in_xml,
                }
                for document in documents
            ],
            "createdAt": invoice.created_at,
            "updatedAt": invoice.updated_at,
            "issuedAt": invoice.issued_at,
        }

    def _serialize_client(self, client: Client) -> ClientRead:
        return ClientRead(
            id=str(client.id),
            clientType=InvoiceClientType(client.client_type.value.lower()),
            firstName=client.first_name,
            lastName=client.last_name,
            companyName=client.company_name,
            vatNumber=client.vat_number,
            taxCode=client.tax_code,
            address=client.address,
            city=client.city,
            postalCode=client.postal_code,
            province=client.province,
            country=client.country,
            pec=client.pec,
            recipientCode=client.recipient_code,
            createdAt=client.created_at,
            updatedAt=client.updated_at,
        )
