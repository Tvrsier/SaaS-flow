from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.invoices.domain.enums import DocumentType, PaymentMethod, SubjectType
from app.modules.invoices.schemas.request import InvoiceCreatePayload, InvoiceLinePayload



@dataclass(slots=True)
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def is_warning(self) -> bool:
        return len(self.warnings) > 0


class InvoiceValidator:
    def validate(self, invoice: InvoiceCreatePayload) -> ValidationResult:
        result = ValidationResult()

        self._validate_parties(invoice, result)
        self._validate_lines(invoice, result)
        self._validate_payment(invoice, result)
        self._validate_document_type_rules(invoice, result)
        self._validate_stamp_duty(invoice, result)

        return result

    def _validate_parties(self, invoice: InvoiceCreatePayload, result: ValidationResult) -> None:
        issuer = invoice.issuer
        customer = invoice.customer

        if issuer.subject_type == SubjectType.COMPANY and not issuer.company_name:
            result.errors.append("Issuer company_name is required for company subject.")

        if issuer.subject_type == SubjectType.INDIVIDUAL and (not issuer.first_name or not issuer.last_name):
            result.errors.append("Issuer first_name and last_name are required for individual subject.")

        if customer.subject_type == SubjectType.COMPANY and not customer.company_name:
            result.errors.append("Customer company_name is required for company subject.")

        if customer.subject_type == SubjectType.INDIVIDUAL and (not customer.first_name or not customer.last_name):
            result.errors.append("Customer first_name and last_name are required for individual subject.")

        if not customer.vat_number and not customer.tax_code:
            result.errors.append("Customer must have either vat_number or tax_code.")

        if not customer.recipient_code and not customer.pec:
            result.warnings.append("Customer must have either recipient_code or pec.")

        if issuer.subject_type == SubjectType.COMPANY and not issuer.fiscal_regime:
            result.errors.append("Issuer fiscal_regime is required for company subject.")

    def _validate_lines(self, invoice: InvoiceCreatePayload, result: ValidationResult) -> None:
        if not invoice.items:
            result.errors.append("Invoice must contain at least one line.")
            return

        line_numbers = set()

        for item in invoice.items:
            if item.line_number in line_numbers:
                result.errors.append(f"Line number {item.line_number} is duplicated.")
            else:
                line_numbers.add(item.line_number)

            self._validate_single_line(item, result)

    @staticmethod
    def _validate_single_line(item: InvoiceLinePayload, result: ValidationResult) -> None:
        if item.quantity <= 0:
            result.errors.append(f"Line {item.line_number} Quantity must be greater than 0.")

        if item.vat_rate == 0 and item.nature is None:
            result.errors.append(f"Line {item.line_number} nature is required when vat_rate is 0.")

        if item.vat_rate > 0 and item.nature is not None:
            result.errors.append(f"Line {item.line_number} nature must be null when vat_rate is greater than 0.")

    @staticmethod
    def _validate_payment(invoice: InvoiceCreatePayload, result: ValidationResult):
        payment = invoice.payment

        if payment.payment_method == PaymentMethod.MP05 and not payment.iban:
            result.warnings.append("Payment method is wire transfer, but IBAN is not provided.")

        if payment.iban and not payment.beneficiary:
            result.warnings.append("IBAN is provided, but payment beneficiary is missing.")

    def _validate_document_type_rules(self, invoice: InvoiceCreatePayload, result: ValidationResult):
        if invoice.document_type == DocumentType.TD04:
            self._validate_credit_note(invoice, result)
        else:
            self._validate_standard_document(invoice, result)

    @staticmethod
    def _validate_credit_note(invoice: InvoiceCreatePayload, result: ValidationResult):
        for item in invoice.items:
            if item.unit_price > 0:
                result.errors.append(f"Line {item.line_number} unit_price must be negative for credit notes.")

            if item.unit_price == 0:
                result.warnings.append(f"Line {item.line_number} unit_price is 0. This may be an error.")

    @staticmethod
    def _validate_standard_document(invoice: InvoiceCreatePayload, result: ValidationResult):
        for item in invoice.items:
            if item.unit_price <= 0:
                result.errors.append(f"Line {item.line_number} unit_price must be positive for standard documents.")

    @staticmethod
    def _validate_stamp_duty(invoice: InvoiceCreatePayload, result: ValidationResult):
        stamp_duty = invoice.stamp_duty

        if stamp_duty.enabled and stamp_duty.amount <= 0:
            result.errors.append("Stamp duty amount must be greater than 0 when enabled.")

        if not stamp_duty.enabled and stamp_duty.amount > 0:
            result.errors.append("Stamp duty amount must be 0 when disabled.")