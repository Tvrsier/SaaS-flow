from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.invoices.domain.enums import PaymentMethod

REQUIRED_PAYMENT_FIELDS: dict[PaymentMethod, tuple[str, ...]] = {
    PaymentMethod.MP05: ("beneficiary", "iban"),
    PaymentMethod.MP11: ("payment_code",),
    PaymentMethod.MP12: ("payment_code",),
    PaymentMethod.MP18: ("payment_code",),
    PaymentMethod.MP19: ("iban", "payment_code"),
    PaymentMethod.MP20: ("iban", "payment_code"),
    PaymentMethod.MP23: ("payment_code",),
}

ALLOWED_PAYMENT_FIELDS: dict[PaymentMethod, tuple[str, ...]] = {
    PaymentMethod.MP05: ("beneficiary", "financial_institution", "iban", "abi", "cab", "bic", "payment_code"),
    PaymentMethod.MP11: ("financial_institution", "abi", "cab", "payment_code"),
    PaymentMethod.MP12: ("financial_institution", "payment_code"),
    PaymentMethod.MP18: ("postal_office_code", "payment_code"),
    PaymentMethod.MP19: ("beneficiary", "iban", "bic", "payment_code"),
    PaymentMethod.MP20: ("beneficiary", "iban", "bic", "payment_code"),
    PaymentMethod.MP23: ("payment_code",),
}


class PaymentDetailsPayload(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    beneficiary: str | None = Field(default=None, max_length=200)
    financial_institution: str | None = Field(default=None, alias="financialInstitution", max_length=200)
    iban: str | None = Field(default=None, max_length=34)
    abi: str | None = Field(default=None, max_length=5)
    cab: str | None = Field(default=None, max_length=5)
    bic: str | None = Field(default=None, max_length=11)
    payment_code: str | None = Field(default=None, alias="paymentCode", max_length=60)
    postal_office_code: str | None = Field(default=None, alias="postalOfficeCode", max_length=20)

    @field_validator(
        "beneficiary",
        "financial_institution",
        "iban",
        "abi",
        "cab",
        "bic",
        "payment_code",
        "postal_office_code",
        mode="before",
    )
    @classmethod
    def normalize_empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("iban")
    @classmethod
    def normalize_iban(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.replace(" ", "").upper()

    @field_validator("bic")
    @classmethod
    def normalize_bic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()

    @field_validator("abi", "cab")
    @classmethod
    def validate_abi_cab(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"\d{5}", value):
            raise ValueError("must be exactly 5 digits")
        return value

    def provided_fields(self) -> set[str]:
        return {
            field_name
            for field_name in type(self).model_fields
            if getattr(self, field_name) is not None
        }


class UserPaymentProfileCreate(PaymentDetailsPayload):
    payment_method: PaymentMethod = Field(alias="paymentMethod")


class UserPaymentProfileResponse(PaymentDetailsPayload):
    payment_method: PaymentMethod = Field(alias="paymentMethod")


def validate_payment_details_for_method(payment_method: PaymentMethod, payment_details: PaymentDetailsPayload | None) -> None:
    required_fields = REQUIRED_PAYMENT_FIELDS.get(payment_method)
    allowed_fields = ALLOWED_PAYMENT_FIELDS.get(payment_method, tuple())

    if required_fields is None:
        if payment_details is None:
            return
        if payment_details.provided_fields():
            raise ValueError(f"paymentDetails must be null for payment method {payment_method.value}")
        return

    if payment_details is None:
        raise ValueError(f"paymentDetails is required for payment method {payment_method.value}")

    provided_fields = payment_details.provided_fields()

    missing_fields = [field_name for field_name in required_fields if field_name not in provided_fields]
    if missing_fields:
        raise ValueError(
            f"paymentDetails missing required fields for payment method {payment_method.value}: {', '.join(missing_fields)}"
        )

    not_allowed_fields = sorted(provided_fields - set(allowed_fields))
    if not_allowed_fields:
        raise ValueError(
            f"paymentDetails contains fields not allowed for payment method {payment_method.value}: {', '.join(not_allowed_fields)}"
        )
