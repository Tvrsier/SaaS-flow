from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AddressDTO:
    street: str
    street_number: str | None
    postal_code: str | None
    city: str | None
    province: str | None
    country: str


@dataclass(frozen=True, slots=True)
class PartyDTO:
    name: str
    first_name: str | None
    last_name: str | None
    vat_number: str | None
    tax_code: str | None
    address: AddressDTO
    email: str | None = None
    recipient_code: str | None = None
    pec: str | None = None


@dataclass(frozen=True, slots=True)
class InvoiceLineDTO:
    number: int
    description: str
    quantity: Decimal
    unit_of_measure: str | None
    unit_price: Decimal
    taxable_amount: Decimal
    vat_rate: Decimal
    vat_nature: str | None
    vat_amount: Decimal
    total_amount: Decimal


@dataclass(frozen=True, slots=True)
class VatSummaryDTO:
    vat_rate: Decimal
    vat_nature: str | None
    taxable_amount: Decimal
    vat_amount: Decimal


@dataclass(frozen=True, slots=True)
class PaymentDetailsDTO:
    method: str
    due_date: date
    amount: Decimal
    beneficiary: str | None
    financial_institution: str | None
    iban: str | None
    abi: str | None
    cab: str | None
    bic: str | None
    payment_code: str | None
    postal_office_code: str | None


@dataclass(frozen=True, slots=True)
class RelatedDocumentDTO:
    document_type: str
    document_number: str | None
    document_date: date | None
    line_numbers: tuple[int, ...]
    metadata: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class InvoiceDocumentDTO:
    invoice_id: UUID
    invoice_number: str
    issue_date: date
    document_type: str
    currency: str
    seller: PartyDTO
    customer: PartyDTO
    lines: tuple[InvoiceLineDTO, ...]
    vat_summaries: tuple[VatSummaryDTO, ...]
    payment_details: PaymentDetailsDTO | None
    related_documents: tuple[RelatedDocumentDTO, ...]
    ddt: tuple[dict[str, object], ...]
    taxable_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    vat_collectability: str
