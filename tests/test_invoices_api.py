from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any, Generator, cast
from uuid import uuid4

warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.auth import create_access_token  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.models.invoice import Client, Invoice  # noqa: E402
from app.db.models.user import AccountType, User  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    overrides = cast(Any, app).dependency_overrides
    overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        overrides.clear()


@pytest.fixture()
def company_user(db_session: Session) -> User:
    user = User(
        id=uuid4(),
        email="company@example.com",
        account_type=AccountType.azienda,
        company_name="GestPro SRL",
        codice_fiscale="01234567890",
        partita_iva="01234567890",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(company_user: User) -> dict[str, str]:
    token = create_access_token(company_user.id, company_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def invoice_payload() -> dict[str, object]:
    return {
        "mode": 1,
        "invoiceNumber": "2026-001",
        "issueDate": "2026-05-15",
        "currency": "EUR",
        "documentType": "TD01",
        "client": {
            "clientType": "company",
            "companyName": "Demo S.r.l.",
            "vatNumber": "12345678901",
            "taxCode": "01234567890",
            "address": "Via Roma 1",
            "city": "Milano",
            "postalCode": "20100",
            "province": "MI",
            "country": "IT",
        },
        "lines": [
            {
                "numberLine": 1,
                "description": "Servizio consulenza",
                "quantity": 2,
                "unitMeasure": "h",
                "unitPrice": 50,
                "lineTotal": 100,
                "vatRate": 22,
            }
        ],
        "subtotal": 100,
        "vatTotal": 22,
        "total": 122,
        "attachments": [],
    }


def test_create_invoice_persists_invoice_client_lines(client: TestClient, auth_headers: dict[str, str], db_session: Session, invoice_payload: dict[str, object]):
    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["invoiceNumber"] == "2026-001"
    assert body["status"] == "DRAFT"
    assert body["client"]["clientType"] == "company"
    assert body["client"]["clientCode"] == "12345678901"
    assert body["lines"][0]["numberLine"] == 1
    assert body["vatSummary"][0]["vatRate"] in ("22.00", 22, 22.0)

    invoice = db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-001"))
    assert invoice is not None
    assert invoice.client_id is not None

    client_row = db_session.get(Client, invoice.client_id)
    assert client_row is not None


def test_get_invoices_returns_created_invoice(client: TestClient, auth_headers: dict[str, str], invoice_payload: dict[str, object]):
    created = client.post("/invoices", json=invoice_payload, headers=auth_headers)
    assert created.status_code == 201

    response = client.get("/invoices", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert body["lastInvoiceNumber"] == "2026-001"
    assert len(body["data"]) >= 1
    assert any(item["invoiceNumber"] == "2026-001" and item["client"]["clientCode"] == "12345678901" for item in body["data"])


def test_create_invoice_rejects_totals_mismatch(client: TestClient, auth_headers: dict[str, str], invoice_payload: dict[str, object]):
    invoice_payload = dict(invoice_payload)
    invoice_payload["total"] = 999

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 422
