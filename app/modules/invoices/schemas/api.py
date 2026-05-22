from __future__ import annotations

from base64 import b64decode
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, IntEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.invoices.domain.enums import DocumentType, NatureCode

TWOPLACES = Decimal("0.01")


class InvoiceMode(IntEnum):
    SEND = 0
    DRAFT = 1


class InvoiceClientType(str, Enum):
    PRIVATE = "private"
    COMPANY = "company"
    PUBLIC_ADMINISTRATION = "public_administration"


class InvoiceCurrency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"


class InvoiceClientPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    client_type: InvoiceClientType = Field(alias="clientType")
    first_name: str | None = Field(default=None, alias="firstName", max_length=100)
    last_name: str | None = Field(default=None, alias="lastName", max_length=100)
    company_name: str | None = Field(default=None, alias="companyName", max_length=255)
    vat_number: str | None = Field(default=None, alias="vatNumber", max_length=20)
    tax_code: str | None = Field(default=None, alias="taxCode", max_length=20)
    address: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., alias="postalCode", min_length=1, max_length=20)
    province: str = Field(..., min_length=1, max_length=10)
    country: str = Field(default="IT", min_length=1, max_length=2)
    pec: str | None = Field(default=None, max_length=255)
    recipient_code: str | None = Field(default=None, alias="recipientCode", max_length=7)

    @field_validator("vat_number", "tax_code", "recipient_code", "country")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper().replace(" ", "")
        return normalized or None

    @model_validator(mode="after")
    def validate_client(self) -> "InvoiceClientPayload":
        if self.client_type == InvoiceClientType.PRIVATE:
            if not self.first_name:
                raise ValueError("firstName is required for private clients")
            if not self.last_name:
                raise ValueError("lastName is required for private clients")
            if not self.tax_code:
                raise ValueError("taxCode is required for private clients")
            if self.vat_number not in {None, ""}:
                raise ValueError("vatNumber must be null for private clients")
            if not self.recipient_code:
                self.recipient_code = "0000000"
        elif self.client_type == InvoiceClientType.COMPANY:
            if not self.company_name:
                raise ValueError("companyName is required for company clients")
            if not self.vat_number:
                raise ValueError("vatNumber is required for company clients")
            if not self.recipient_code:
                self.recipient_code = "0000000"
        elif self.client_type == InvoiceClientType.PUBLIC_ADMINISTRATION:
            if not self.company_name:
                raise ValueError("companyName is required for public administration clients")
            if not self.tax_code:
                raise ValueError("taxCode is required for public administration clients")
            if not self.recipient_code:
                raise ValueError("recipientCode is required for public administration clients")
            if len(self.recipient_code) != 6:
                raise ValueError("recipientCode must be 6 characters for public administration clients")
        return self


class InvoiceLinePayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    number_line: int = Field(..., alias="numberLine", ge=1)
    description: str = Field(..., min_length=1, max_length=1000)
    quantity: Decimal = Field(..., gt=Decimal("0"))
    unit_measure: str | None = Field(default=None, alias="unitMeasure", max_length=10)
    unit_price: Decimal = Field(..., alias="unitPrice", ge=Decimal("0"))
    line_total: Decimal = Field(..., alias="lineTotal", ge=Decimal("0"))
    vat_rate: Decimal = Field(..., alias="vatRate", ge=Decimal("0"), le=Decimal("100"))
    nature: NatureCode | None = None

    @field_validator("unit_measure")
    @classmethod
    def normalize_unit_measure(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_line(self) -> "InvoiceLinePayload":
        expected_total = (self.quantity * self.unit_price).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        provided_total = self.line_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if expected_total != provided_total:
            raise ValueError("lineTotal must equal quantity * unitPrice")
        if self.vat_rate == Decimal("0") and self.nature is None:
            raise ValueError("nature is required when vatRate is 0")
        if self.vat_rate > Decimal("0") and self.nature is not None:
            raise ValueError("nature must be null when vatRate is greater than 0")
        return self


class InvoiceAttachmentPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    file_name: str = Field(..., alias="fileName", min_length=1, max_length=255)
    mime_type: str = Field(..., alias="mimeType", min_length=1, max_length=255)
    content_base64: str = Field(..., alias="contentBase64", min_length=1)
    size: int = Field(..., ge=0)

    @field_validator("content_base64")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        b64decode(value, validate=True)
        return value


class InvoiceCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    mode: InvoiceMode
    invoice_number: str = Field(..., alias="invoiceNumber", min_length=1, max_length=20)
    issue_date: date = Field(..., alias="issueDate")
    currency: InvoiceCurrency
    document_type: DocumentType = Field(..., alias="documentType")
    client: InvoiceClientPayload
    lines: list[InvoiceLinePayload] = Field(..., min_length=1)
    subtotal: Decimal = Field(..., ge=Decimal("0"))
    vat_total: Decimal = Field(..., alias="vatTotal", ge=Decimal("0"))
    total: Decimal = Field(..., ge=Decimal("0"))
    attachments: list[InvoiceAttachmentPayload] = Field(default_factory=list)

    @field_validator("invoice_number")
    @classmethod
    def normalize_invoice_number(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_totals(self) -> "InvoiceCreateRequest":
        subtotal = self.subtotal.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        vat_total = self.vat_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total = self.total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        calculated_subtotal = sum((line.line_total for line in self.lines), Decimal("0.00")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        calculated_vat = sum(((line.line_total * line.vat_rate) / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP) for line in self.lines).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        calculated_total = (calculated_subtotal + calculated_vat).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if subtotal != calculated_subtotal:
            raise ValueError("subtotal does not match invoice lines")
        if vat_total != calculated_vat:
            raise ValueError("vatTotal does not match invoice lines")
        if total != calculated_total:
            raise ValueError("total does not match subtotal + vatTotal")
        return self


class InvoiceClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    client_type: InvoiceClientType = Field(alias="clientType")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    company_name: str | None = Field(default=None, alias="companyName")
    vat_number: str | None = Field(default=None, alias="vatNumber")
    tax_code: str | None = Field(default=None, alias="taxCode")
    client_code: str | None = Field(default=None, alias="clientCode")
    address: str
    city: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    province: str | None = None
    country: str
    pec: str | None = None
    recipient_code: str | None = Field(default=None, alias="recipientCode")


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    line_number: int = Field(alias="numberLine")
    description: str
    quantity: Decimal
    unit_measure: str | None = Field(default=None, alias="unitMeasure")
    unit_price: Decimal = Field(alias="unitPrice")
    line_total: Decimal = Field(alias="lineTotal")
    vat_rate: Decimal = Field(alias="vatRate")
    nature: NatureCode | None = None


class InvoiceAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    file_name: str = Field(alias="fileName")
    mime_type: str = Field(alias="mimeType")
    file_format: str = Field(alias="fileFormat")
    size: int
    s3_key: str = Field(alias="s3Key")
    hash: str
    included_in_xml: bool = Field(alias="includedInXml")
    description: str | None = None


class InvoiceVatSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    vat_rate: Decimal = Field(alias="vatRate")
    nature: NatureCode | None = None
    taxable_amount: Decimal = Field(alias="taxableAmount")
    vat_amount: Decimal = Field(alias="vatAmount")


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    company_id: str = Field(alias="companyId")
    client_id: str | None = Field(default=None, alias="clientId")
    invoice_number: str = Field(alias="invoiceNumber")
    invoice_year: int = Field(alias="invoiceYear")
    invoice_section: str | None = Field(default=None, alias="invoiceSection")
    document_type: DocumentType = Field(alias="documentType")
    status: str
    issue_date: date = Field(alias="issueDate")
    due_date: date | None = Field(default=None, alias="dueDate")
    currency: str
    notes: str | None = None
    taxable_amount: Decimal = Field(alias="taxableAmount")
    vat_amount: Decimal = Field(alias="vatAmount")
    total_amount: Decimal = Field(alias="totalAmount")
    withholding_amount: Decimal = Field(alias="withholdingAmount")
    stamp_duty_amount: Decimal = Field(alias="stampDutyAmount")
    rounding_amount: Decimal = Field(alias="roundingAmount")
    client: InvoiceClientRead
    lines: list[InvoiceLineRead]
    vat_summary: list[InvoiceVatSummaryRead] = Field(default_factory=list, alias="vatSummary")
    attachments: list[InvoiceAttachmentRead] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    issued_at: datetime | None = Field(default=None, alias="issuedAt")


class InvoicesListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: list[InvoiceRead]
    last_invoice_number: str | None = Field(default=None, alias="lastInvoiceNumber")
    page: int | None = None
    per_page: int | None = Field(default=None, alias="perPage")
    total: int | None = None
    count: int | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    id: str
    client_type: InvoiceClientType = Field(alias="clientType")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    company_name: str | None = Field(default=None, alias="companyName")
    vat_number: str | None = Field(default=None, alias="vatNumber")
    tax_code: str | None = Field(default=None, alias="taxCode")
    address: str
    city: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    province: str | None = None
    country: str
    pec: str | None = None
    recipient_code: str | None = Field(default=None, alias="recipientCode")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ClientsListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    data: list[ClientRead]
