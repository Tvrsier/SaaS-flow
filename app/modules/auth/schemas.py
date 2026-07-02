from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.invoices.schemas.payment import UserPaymentProfileResponse
from app.schemas.user import UserRead


class AuthRegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    name: str | None = None
    surname: str | None = None
    email: EmailStr
    companyName: str | None = None
    partitaIva: str | None = None
    codiceFiscale: str | None = None
    phone: str | None = None
    payment_profiles: list[UserPaymentProfileResponse] = Field(default_factory=list, alias="paymentProfiles")
