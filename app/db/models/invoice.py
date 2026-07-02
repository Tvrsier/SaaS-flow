from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, BigInteger, CheckConstraint, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.user import User
from app.modules.invoices.domain.enums import ClientType, DocumentType, EsigibilitaIVA, InvoiceStatus, NatureCode, PaymentMethod, PaymentStatus


class UUIDTimestampMixin:
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Client(Base, UUIDTimestampMixin):
    __tablename__ = "clients"
    __table_args__ = (
        CheckConstraint(
            "client_type <> 'PRIVATE' OR (first_name IS NOT NULL AND last_name IS NOT NULL AND tax_code IS NOT NULL AND vat_number IS NULL AND recipient_code = '0000000')",
            name="ck_clients_private_required_fields",
        ),
        CheckConstraint(
            "client_type <> 'COMPANY' OR (company_name IS NOT NULL AND vat_number IS NOT NULL)",
            name="ck_clients_company_required_fields",
        ),
        CheckConstraint(
            "client_type <> 'PUBLIC_ADMINISTRATION' OR (company_name IS NOT NULL AND tax_code IS NOT NULL AND recipient_code IS NOT NULL AND char_length(recipient_code) = 6)",
            name="ck_clients_pa_required_fields",
        ),
        Index("ix_clients_company_id", "company_id"),
        Index("ix_clients_client_type", "client_type"),
        Index("ix_clients_deleted_at", "deleted_at"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    client_type: Mapped[ClientType] = mapped_column(SAEnum(ClientType, name="client_type"), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    vat_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    province: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="IT", server_default=text("'IT'"))

    pec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_code: Mapped[str | None] = mapped_column(String(7), nullable=True, default="0000000", server_default=text("'0000000'"))

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    company: Mapped[User] = relationship("User", back_populates="clients")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="client", foreign_keys="Invoice.client_id")


class Invoice(Base, UUIDTimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("status = 'DRAFT' OR invoice_number IS NOT NULL", name="ck_invoices_invoice_number_required"),
        CheckConstraint("taxable_amount >= 0", name="ck_invoices_taxable_amount_non_negative"),
        CheckConstraint("vat_amount >= 0", name="ck_invoices_vat_amount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_invoices_total_amount_non_negative"),
        CheckConstraint("withholding_amount >= 0", name="ck_invoices_withholding_amount_non_negative"),
        CheckConstraint("stamp_duty_amount >= 0", name="ck_invoices_stamp_duty_amount_non_negative"),
        Index("ix_invoices_company_id", "company_id"),
        Index("ix_invoices_client_id", "client_id"),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_issue_date", "issue_date"),
        Index("ix_invoices_status", "status"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    client_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    client: Mapped[Client | None] = relationship(back_populates="invoices", foreign_keys=[client_id])

    invoice_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_year: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_section: Mapped[str | None] = mapped_column(String(20), nullable=True)

    document_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType, name="invoice_document_type"), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )

    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default=text("'EUR'"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    withholding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    stamp_duty_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    rounding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))

    xml_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    xml_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    xml_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    esigibilita_iva: Mapped[EsigibilitaIVA | None] = mapped_column(
        SAEnum(EsigibilitaIVA, name="esigibilita_iva_type", values_callable=lambda obj: [e.value for e in obj]), nullable=True
    )

    invoice_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payments: Mapped[list["InvoicePayment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    payment_details: Mapped["InvoicePaymentDetails | None"] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        uselist=False,
    )


class InvoiceLine(Base, UUIDTimestampMixin):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint("invoice_id", "line_number", name="uq_invoice_lines_invoice_line_number"),
        CheckConstraint("line_number > 0", name="ck_invoice_lines_line_number_positive"),
        CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price_non_negative"),
        CheckConstraint("COALESCE(discount_amount, 0) >= 0", name="ck_invoice_lines_discount_amount_non_negative"),
        CheckConstraint("COALESCE(discount_percentage, 0) >= 0 AND COALESCE(discount_percentage, 0) <= 100", name="ck_invoice_lines_discount_percentage_range"),
        CheckConstraint("vat_rate >= 0", name="ck_invoice_lines_vat_rate_non_negative"),
        CheckConstraint("taxable_amount >= 0", name="ck_invoice_lines_taxable_amount_non_negative"),
        CheckConstraint("vat_amount >= 0", name="ck_invoice_lines_vat_amount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_invoice_lines_total_amount_non_negative"),
        Index("ix_invoice_lines_invoice_id", "invoice_id"),
    )

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    discount_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_nature: Mapped[NatureCode | None] = mapped_column(SAEnum(NatureCode, name="invoice_vat_nature"), nullable=True)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(20), nullable=True)


class InvoiceVatSummary(Base, UUIDTimestampMixin):
    __tablename__ = "invoice_vat_summary"
    __table_args__ = (
        Index("ix_invoice_vat_summary_invoice_id", "invoice_id"),
        UniqueConstraint("invoice_id", "vat_rate", "vat_nature", name="uq_invoice_vat_summary_invoice_rate_nature"),
    )

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_nature: Mapped[NatureCode | None] = mapped_column(SAEnum(NatureCode, name="invoice_vat_nature"), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class InvoicePayment(Base, UUIDTimestampMixin):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_invoice_payments_amount_non_negative"),
        CheckConstraint("paid_amount >= 0", name="ck_invoice_payments_paid_amount_non_negative"),
        CheckConstraint("paid_amount <= amount", name="ck_invoice_payments_paid_amount_not_exceed_amount"),
        Index("ix_invoice_payments_invoice_id", "invoice_id"),
    )

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="invoice_payment_method"), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="invoice_payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=text("'PENDING'"),
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class InvoicePaymentDetails(Base):
    __tablename__ = "invoice_payment_details"

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True)
    beneficiary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    financial_institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    abi: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cab: Mapped[str | None] = mapped_column(String(5), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    payment_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    postal_office_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="payment_details")


class InvoiceDocument(Base, UUIDTimestampMixin):
    __tablename__ = "invoice_documents"
    __table_args__ = (
        Index("ix_invoice_documents_invoice_id", "invoice_id"),
        Index("ix_invoice_documents_xml_block", "xml_block"),
    )

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    xml_block: Mapped[str] = mapped_column(String(64), nullable=False, default="ALLEGATI", server_default=text("'ALLEGATI'"))

    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    document_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_line_numbers: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    document_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_in_xml: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


# Compatibilità retroattiva: il vecchio nome continua a puntare allo stesso modello
InvoiceAttachment = InvoiceDocument


Index(
    "ux_invoices_company_year_section_number_active",
    Invoice.company_id,
    Invoice.invoice_year,
    func.coalesce(Invoice.invoice_section, ""),
    Invoice.invoice_number,
    unique=True,
    postgresql_where=Invoice.deleted_at.is_(None),
)

class PassiveInvoice(Base, UUIDTimestampMixin):
    __tablename__ = "passive_invoices"
    __table_args__ = (
        CheckConstraint("taxable_amount >= 0", name="ck_passive_invoices_taxable_amount_non_negative"),
        CheckConstraint("vat_amount >= 0", name="ck_passive_invoices_vat_amount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_passive_invoices_total_amount_non_negative"),
        Index("ix_passive_invoices_company_id", "company_id"),
        Index("ix_passive_invoices_supplier_id", "supplier_id"),
        Index("ix_passive_invoices_invoice_date", "invoice_date"),
        Index("ix_passive_invoices_registration_date", "registration_date"),
        Index("ix_passive_invoices_vat_competence_date", "vat_competence_date"),
        Index("ix_passive_invoices_status", "status"),
        Index("ix_passive_invoices_xml_hash", "xml_hash"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    supplier_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)

    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_vat_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supplier_tax_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supplier_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supplier_province: Mapped[str | None] = mapped_column(String(10), nullable=True)
    supplier_country: Mapped[str] = mapped_column(String(2), nullable=False, default="IT", server_default=text("'IT'"))

    invoice_number: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_year: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    vat_competence_date: Mapped[date] = mapped_column(Date, nullable=False)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default=text("'EUR'"))
    document_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType, name="invoice_document_type"), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )

    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))

    xml_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    xml_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)

    esigibilita_iva: Mapped[EsigibilitaIVA | None] = mapped_column(
        SAEnum(EsigibilitaIVA, name="esigibilita_iva_type", values_callable=lambda obj: [e.value for e in obj]), nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped[User] = relationship("User")
    supplier: Mapped[Client | None] = relationship("Client", foreign_keys=[supplier_id])


class PassiveInvoiceLine(Base, UUIDTimestampMixin):
    __tablename__ = "passive_invoice_lines"
    __table_args__ = (
        UniqueConstraint("passive_invoice_id", "line_number", name="uq_passive_invoice_lines_invoice_line_number"),
        CheckConstraint("line_number > 0", name="ck_passive_invoice_lines_line_number_positive"),
        CheckConstraint("quantity > 0", name="ck_passive_invoice_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_passive_invoice_lines_unit_price_non_negative"),
        CheckConstraint("COALESCE(discount_amount, 0) >= 0", name="ck_passive_invoice_lines_discount_amount_non_negative"),
        CheckConstraint("COALESCE(discount_percentage, 0) >= 0 AND COALESCE(discount_percentage, 0) <= 100", name="ck_passive_invoice_lines_discount_percentage_range"),
        CheckConstraint("vat_rate >= 0", name="ck_passive_invoice_lines_vat_rate_non_negative"),
        CheckConstraint("taxable_amount >= 0", name="ck_passive_invoice_lines_taxable_amount_non_negative"),
        CheckConstraint("vat_amount >= 0", name="ck_passive_invoice_lines_vat_amount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_passive_invoice_lines_total_amount_non_negative"),
        Index("ix_passive_invoice_lines_passive_invoice_id", "passive_invoice_id"),
    )

    passive_invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("passive_invoices.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    discount_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_nature: Mapped[NatureCode | None] = mapped_column(SAEnum(NatureCode, name="invoice_vat_nature"), nullable=True)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_of_measure: Mapped[str | None] = mapped_column(String(20), nullable=True)


class PassiveInvoiceVatSummary(Base, UUIDTimestampMixin):
    __tablename__ = "passive_invoice_vat_summary"
    __table_args__ = (
        Index("ix_passive_invoice_vat_summary_passive_invoice_id", "passive_invoice_id"),
        UniqueConstraint("passive_invoice_id", "vat_rate", "vat_nature", name="uq_passive_invoice_vat_summary_invoice_rate_nature"),
    )

    passive_invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("passive_invoices.id", ondelete="CASCADE"), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_nature: Mapped[NatureCode | None] = mapped_column(SAEnum(NatureCode, name="invoice_vat_nature"), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class VatPeriod(Base, UUIDTimestampMixin):
    __tablename__ = "vat_periods"
    __table_args__ = (
        CheckConstraint("period_index > 0", name="ck_vat_periods_period_index_positive"),
        CheckConstraint("(frequency = 'MONTHLY' AND period_index BETWEEN 1 AND 12) OR (frequency = 'QUARTERLY' AND period_index BETWEEN 1 AND 4)", name="ck_vat_periods_period_index_valid"),
        CheckConstraint("previous_credit >= 0", name="ck_vat_periods_previous_credit_non_negative"),
        UniqueConstraint("company_id", "year", "period_index", "frequency", name="uq_vat_periods_company_year_period_frequency"),
        Index("ix_vat_periods_company_id", "company_id"),
        Index("ix_vat_periods_status", "status"),
        Index("ix_vat_periods_company_year_frequency", "company_id", "year", "frequency"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", server_default=text("'OPEN'"))
    previous_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped[User] = relationship("User")


class VatMovement(Base, UUIDTimestampMixin):
    __tablename__ = "vat_movements"
    __table_args__ = (
        CheckConstraint("vat_rate >= 0", name="ck_vat_movements_vat_rate_non_negative"),
        CheckConstraint("taxable_amount >= 0", name="ck_vat_movements_taxable_amount_non_negative"),
        CheckConstraint("vat_amount >= 0", name="ck_vat_movements_vat_amount_non_negative"),
        Index("ix_vat_movements_company_id", "company_id"),
        Index("ix_vat_movements_period_id", "period_id"),
        Index("ix_vat_movements_source_type", "source_type"),
        Index("ix_vat_movements_movement_type", "movement_type"),
        Index("ix_vat_movements_vat_competence_date", "vat_competence_date"),
        Index("ix_vat_movements_source_invoice_id", "source_invoice_id"),
        Index("ix_vat_movements_source_passive_invoice_id", "source_passive_invoice_id"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vat_periods.id", ondelete="RESTRICT"), nullable=False)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_invoice_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    source_passive_invoice_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("passive_invoices.id", ondelete="SET NULL"), nullable=True)

    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    vat_competence_date: Mapped[date] = mapped_column(Date, nullable=False)

    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_nature: Mapped[NatureCode | None] = mapped_column(SAEnum(NatureCode, name="invoice_vat_nature"), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    company: Mapped[User] = relationship("User")
    period: Mapped[VatPeriod] = relationship("VatPeriod")
    source_invoice: Mapped[Invoice | None] = relationship("Invoice", foreign_keys=[source_invoice_id])
    source_passive_invoice: Mapped[PassiveInvoice | None] = relationship("PassiveInvoice", foreign_keys=[source_passive_invoice_id])


class VatSettlement(Base, UUIDTimestampMixin):
    __tablename__ = "vat_settlements"
    __table_args__ = (
        CheckConstraint("total_debit >= 0", name="ck_vat_settlements_total_debit_non_negative"),
        CheckConstraint("total_credit >= 0", name="ck_vat_settlements_total_credit_non_negative"),
        CheckConstraint("previous_credit >= 0", name="ck_vat_settlements_previous_credit_non_negative"),
        CheckConstraint("amount_paid >= 0", name="ck_vat_settlements_amount_paid_non_negative"),
        CheckConstraint("credit_to_carry >= 0", name="ck_vat_settlements_credit_to_carry_non_negative"),
        UniqueConstraint("period_id", name="uq_vat_settlements_period_id"),
        Index("ix_vat_settlements_company_id", "company_id"),
        Index("ix_vat_settlements_period_id", "period_id"),
        Index("ix_vat_settlements_payment_status", "payment_status"),
    )

    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vat_periods.id", ondelete="RESTRICT"), nullable=False)

    total_debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    previous_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount_to_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    credit_to_carry: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default=text("0"))

    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNPAID", server_default=text("'UNPAID'"))
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company: Mapped[User] = relationship("User")
    period: Mapped[VatPeriod] = relationship("VatPeriod")


__all__ = [
    "Client",
    "Invoice",
    "InvoiceLine",
    "InvoiceVatSummary",
    "InvoicePayment",
    "InvoicePaymentDetails",
    "InvoiceDocument",
    "InvoiceAttachment",
    "PassiveInvoice",
    "PassiveInvoiceLine",
    "PassiveInvoiceVatSummary",
    "VatPeriod",
    "VatMovement",
    "VatSettlement",
]
