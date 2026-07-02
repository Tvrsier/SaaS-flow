from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.invoices.schemas.payment import UserPaymentProfileCreate
from app.db.models.user import AccountType


class UserBase(BaseModel):
    email: EmailStr
    account_type: AccountType = Field(alias="accountType")
    phone: str | None = None
    mobile: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class UserCreate(BaseModel):
    account_type: AccountType = Field(alias="accountType")
    email: EmailStr
    password: str
    codice_fiscale: str | None = Field(default=None, alias="codiceFiscale")
    partita_iva: str | None = Field(default=None, alias="partitaIva")
    phone: str | None = None
    mobile: str | None = None

    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    nationality: str | None = None
    birth_date: str | None = Field(default=None, alias="birthDate")
    birth_province: str | None = Field(default=None, alias="birthProvince")
    birth_comune: str | None = Field(default=None, alias="birthComune")

    company_name: str | None = Field(default=None, alias="companyName")

    legal_address: str | None = Field(default=None, alias="legalAddress")
    residence_country: str | None = Field(default=None, alias="residenceCountry")
    residence_province: str | None = Field(default=None, alias="residenceProvince")
    residence_comune: str | None = Field(default=None, alias="residenceComune")
    residence_postal: str | None = Field(default=None, alias="residencePostal")
    payment_profiles: list[UserPaymentProfileCreate] = Field(default_factory=list, alias="paymentProfiles")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters long")
        return value

    @model_validator(mode="after")
    def validate_required_fields(self) -> "UserCreate":
        if self.account_type in {AccountType.privato, AccountType.libero_professionista, AccountType.ditta_individuale}:
            if not self.first_name:
                raise ValueError("firstName is required for this account type")
            if not self.last_name:
                raise ValueError("lastName is required for this account type")
            if not self.codice_fiscale:
                raise ValueError("codiceFiscale is required for this account type")
        if self.account_type in {AccountType.azienda, AccountType.pubblica_amministrazione}:
            if not self.company_name:
                raise ValueError("companyName is required for this account type")
            if not self.legal_address:
                raise ValueError("legalAddress is required for this account type")
            if not self.residence_country:
                raise ValueError("residenceCountry is required for this account type")
            if not self.residence_province:
                raise ValueError("residenceProvince is required for this account type")
            if not self.residence_comune:
                raise ValueError("residenceComune is required for this account type")
            if not self.residence_postal:
                raise ValueError("residencePostal is required for this account type")
            if not self.partita_iva:
                raise ValueError("partitaIva is required for this account type")
        payment_methods = [profile.payment_method for profile in self.payment_profiles]
        if len(payment_methods) != len(set(payment_methods)):
            raise ValueError("paymentProfiles contains duplicated paymentMethod values")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters long")
        return value


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    account_type: AccountType
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    codice_fiscale: str | None = None
    partita_iva: str | None = None
    phone: str | None = None
    mobile: str | None = None
    profile_picture_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    user: UserRead


class UserAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID = Field(alias="userId")
    account_type: AccountType = Field(alias="accountType")
    address_label: str = Field(alias="addressLabel")
    country: str
    province: str | None = None
    city: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    address: str
    street_number: str | None = Field(default=None, alias="streetNumber")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UserAddressesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: list[UserAddressRead]
