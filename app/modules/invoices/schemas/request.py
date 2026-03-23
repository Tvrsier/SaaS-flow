from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List
from app.modules.invoices.domain.enums import *
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class AddressPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    street: str = Field(..., min_length=1, max_length=60, description="Indirizzo (max 60 caratteri)")
    street_number: Optional[str] = Field(default=None, max_length=8, description="Numero civico (max 8 caratteri)")
    zip_code: str = Field(..., min_length=1, max_length=12, description="CAP (5 cifre per Italia, max 12 per estero)")
    city: str = Field(..., min_length=1, max_length=60, description="Comune (max 60 caratteri)")
    province: Optional[str] = Field(default=None, min_length=2, max_length=2, pattern="^[A-Z]{2}$", description="Sigla provincia (2 lettere)")
    country: str = Field(default="IT", min_length=2, max_length=2, pattern="^[A-Z]{2}$", description="Codice paese ISO 3166-1 alpha-2")

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        return value.upper()

    @field_validator("province")
    @classmethod
    def validate_province(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.upper()

    @model_validator(mode='after')
    def validate_italian_address(self):
        """Valida che indirizzi italiani abbiano CAP numerico a 5 cifre"""
        if self.country == "IT":
            if not self.zip_code.isdigit() or len(self.zip_code) != 5:
                raise ValueError("CAP italiano deve essere di 5 cifre numeriche")
        return self


class ContactsPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    pec: Optional[EmailStr] = None


class PartyPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject_type: SubjectType

    company_name: Optional[str] = Field(default=None, min_length=1, max_length=80, description="Denominazione (max 80 caratteri per persone giuridiche)")
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=60, description="Nome (max 60 caratteri per persone fisiche)")
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=60, description="Cognome (max 60 caratteri per persone fisiche)")

    vat_number: Optional[str] = Field(default=None, min_length=2, max_length=30, description="Partita IVA (11 cifre per Italia, max 30 per estero)")
    tax_code: Optional[str] = Field(default=None, min_length=11, max_length=28, description="Codice fiscale (16 caratteri per Italia, max 28 per estero)")

    fiscal_regime: Optional[FiscalRegime] = Field(default=None, description="Regime fiscale del cedente/prestatore")
    recipient_code: Optional[str] = Field(default=None, min_length=7, max_length=7, pattern="^[A-Z0-9]{7}$", description="Codice destinatario (7 caratteri, '0000000' se non disponibile)")
    pec: Optional[EmailStr] = Field(default=None, max_length=256, description="PEC del destinatario")

    address: AddressPayload
    contacts: Optional[ContactsPayload] = None

    @field_validator("vat_number", "tax_code")
    @classmethod
    def normalize_fiscal_codes(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.strip() == "":
            return None
        # Rimuovi spazi e converti in maiuscolo
        normalized = value.strip().upper().replace(" ", "")
        return normalized if normalized else None

    @field_validator("recipient_code")
    @classmethod
    def normalize_recipient_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.strip() == "":
            return None
        # Rimuovi spazi, converti in maiuscolo
        normalized = value.strip().upper().replace(" ", "")
        return normalized if normalized else None

    @model_validator(mode="after")
    def validate_subject_fields(self) -> "PartyPayload":
        if self.subject_type == SubjectType.COMPANY:
            if not self.company_name:
                raise ValueError("company_name is required for company subject")
        elif self.subject_type == SubjectType.INDIVIDUAL:
            if not self.first_name or not self.last_name:
                raise ValueError("first_name and last_name are required for individual subject")

        # Valida formato italiano per soggetti italiani
        if self.address.country == "IT":
            if self.vat_number and (len(self.vat_number) != 11 or not self.vat_number.isdigit()):
                raise ValueError("Partita IVA italiana deve essere di 11 cifre numeriche")
            if self.tax_code and not (11 <= len(self.tax_code) <= 16 and self.tax_code.isalnum()):
                raise ValueError("Codice fiscale italiano deve essere 11-16 caratteri alfanumerici")

        return self


class InvoiceLinePayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    line_number: int = Field(..., ge=1)
    type: LineType

    sku: Optional[str] = Field(default=None, max_length=35, description="Codice articolo (max 35 caratteri)")
    name: str = Field(..., min_length=1, max_length=100, description="Nome breve articolo (max 100 caratteri)")
    description: str = Field(..., min_length=1, max_length=1000, description="Descrizione articolo (max 1000 caratteri)")

    quantity: Decimal = Field(..., gt=Decimal("0"))
    unit_of_measure: Optional[str] = Field(default=None, max_length=20)
    unit_price: Decimal
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"))
    vat_rate: Decimal = Field(default=Decimal("22.00"), ge=Decimal(0), le=Decimal("100"))
    nature: Optional[NatureCode] = Field(default=None)

    @model_validator(mode="after")
    def validate_vat_and_nature(self) -> "InvoiceLinePayload":
        if self.vat_rate == Decimal("0") and self.nature is None:
            raise ValueError("nature is required when vat_rate is 0")

        if self.vat_rate > Decimal("0") and self.nature is not None:
            raise ValueError("nature must be null when vat_rate is greater than 0")

        return self


class StampDutyPayload(BaseModel):
    enabled: bool = False
    amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))

    @model_validator(mode='after')
    def validate_amount(self) -> "StampDutyPayload":
        if not self.enabled and self.amount != Decimal("0.00"):
            raise ValueError("amount must be 0 when stampDuty is disabled")

        return self


class PaymentPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payment_terms: PaymentTerms
    payment_method: PaymentMethod
    due_date: Optional[date] = None
    iban: Optional[str] = Field(default=None, max_length=34)
    beneficiary: Optional[str] = Field(default=None, max_length=120)

    @field_validator("iban")
    @classmethod
    def normalize_iban(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.upper().replace(" ", "")


class InvoiceCreatePayload(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "invoice_number": "FE-2026-000123",
                "invoice_date": "2026-03-08",
                "currency": "EUR",
                "language": "it",
                "document_type": "TD01",
                "causal": [
                    "Vendita prodotti e consulenza"
                ],
                "issuer": {
                    "subject_type": "company",
                    "company_name": "Taverna Tech SRLS",
                    "vat_number": "12345678901",
                    "tax_code": "12345678901",
                    "fiscal_regime": "RF01",
                    "address": {
                        "street": "Via Roma",
                        "street_number": "10",
                        "zip_code": "15121",
                        "city": "Alessandria",
                        "province": "AL",
                        "country": "IT"
                    },
                    "contacts": {
                        "email": "amministrazione@tavernatech.it",
                        "phone": "+39 0131 000000",
                        "pec": "tavernatech@pec.it"
                    }
                },
                "customer": {
                    "subject_type": "individual",
                    "first_name": "Mario",
                    "last_name": "Rossi",
                    "tax_code": "RSSMRA80A01F205X",
                    "recipient_code": "0000000",
                    "pec": "mario.rossi@pec.it",
                    "address": {
                        "street": "Via Verdi",
                        "street_number": "22",
                        "zip_code": "20100",
                        "city": "Milano",
                        "province": "MI",
                        "country": "IT"
                    }
                },
                "items": [
                    {
                        "line_number": 1,
                        "type": "product",
                        "sku": "PROD-001",
                        "name": "Licenza software annuale",
                        "description": "Licenza annuale piattaforma fatturazione",
                        "quantity": "1.00",
                        "unit_of_measure": "NR",
                        "unit_price": "199.00",
                        "discount_percent": "0.00",
                        "vat_rate": "22.00",
                        "nature": None
                    },
                    {
                        "line_number": 2,
                        "type": "service",
                        "sku": "CONS-001",
                        "name": "Setup iniziale",
                        "description": "Configurazione iniziale ambiente cliente",
                        "quantity": "2.00",
                        "unit_of_measure": "H",
                        "unit_price": "50.00",
                        "discount_percent": "0.00",
                        "vat_rate": "22.00",
                        "nature": None
                    }
                ],
                "stamp_duty": {
                    "enabled": False,
                    "amount": "0.00"
                },
                "payment": {
                    "payment_terms": "TP02",
                    "payment_method": "MP05",
                    "due_date": "2026-03-31",
                    "iban": "IT60X0542811101000000123456",
                    "beneficiary": "Taverna Tech SRLS"
                },
                "notes": [
                    "Grazie per l'acquisto"
                ]
            }
        }
    )

    invoice_number: str = Field(..., min_length=1, max_length=20, description="Numero fattura (max 20 caratteri)")
    invoice_date: date
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern="^[A-Z]{3}$", description="Codice valuta ISO 4217 (es. EUR)")
    language: str = Field(default="it", min_length=2, max_length=5)
    document_type: DocumentType

    issuer: PartyPayload
    customer: PartyPayload
    items: List[InvoiceLinePayload] = Field(..., min_length=1)

    payment: PaymentPayload
    stamp_duty: StampDutyPayload = Field(default_factory=StampDutyPayload)

    causal: List[str] = Field(default_factory=list, max_length=20)
    notes: List[str] = Field(default_factory=list, max_length=100)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.lower()

    @field_validator("causal")
    @classmethod
    def clean_causal(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                continue
            if len(item) > 200:
                raise ValueError("each causale entry must be at most 200 characters long")
            cleaned.append(item)
        return cleaned

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                continue
            if len(item) > 1000:
                raise ValueError("each note entry must be at most 1000 characters long")
            cleaned.append(item)
        return cleaned

    @model_validator(mode="after")
    def validate_invoice(self) -> "InvoiceCreatePayload":
        # Validazione line_numbers unici
        line_numbers = [item.line_number for item in self.items]
        if len(line_numbers) != len(set(line_numbers)):
            raise ValueError("line_number must be unique")

        # Validazione identificazione fiscale cliente
        if not self.customer.vat_number and not self.customer.tax_code:
            raise ValueError("customer must have either vat_number or tax_code")

        # Validazione regime fiscale emittente
        if self.issuer.subject_type == SubjectType.COMPANY and not self.issuer.fiscal_regime:
            raise ValueError("issuer must have fiscal_regime when subject_type is company")

        # Validazione codice destinatario o PEC per cliente
        if not self.customer.recipient_code and not self.customer.pec:
            raise ValueError("customer must have either recipient_code or pec for electronic invoice delivery")

        # Validazione partita IVA emittente
        if not self.issuer.vat_number:
            raise ValueError("issuer must have vat_number")

        # Validazione lunghezza causale
        for causale in self.causal:
            if len(causale) > 200:
                raise ValueError("each causale entry must be at most 200 characters long")

        return self

