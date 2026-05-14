from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountType(str, Enum):
    privato = "privato"
    libero_professionista = "libero_professionista"
    azienda = "azienda"
    ditta_individuale = "ditta_individuale"
    pubblica_amministrazione = "pubblica_amministrazione"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_codice_fiscale", "codice_fiscale"),
        Index("ix_users_partita_iva", "partita_iva"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    account_type: Mapped[AccountType] = mapped_column(SAEnum(AccountType, name="account_type"), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    codice_fiscale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    partita_iva: Mapped[str | None] = mapped_column(String(32), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)

    profile_picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    external_auth_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_privacy_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
