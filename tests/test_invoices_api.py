from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any, Generator, cast
from uuid import uuid4

warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.auth import create_access_token  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.models.invoice import Client, Invoice, InvoicePayment  # noqa: E402
from app.db.models.user import AccountType, User  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.invoices.domain.enums import ClientType  # noqa: E402

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    db = TestingSessionLocal(bind=connection)
    transaction = connection.begin()
    db.begin_nested()

    @event.listens_for(db, "after_transaction_end")
    def _restart_savepoint(session: Session, trans) -> None:
        parent = getattr(trans, "parent", None)
        if trans.nested and (parent is None or not parent.nested):
            session.begin_nested()

    try:
        yield db
    finally:
        event.remove(db, "after_transaction_end", _restart_savepoint)
        db.close()
        if transaction.is_active:
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
def customer_user(db_session: Session) -> User:
    user = User(
        id=uuid4(),
        email="customer@example.com",
        account_type=AccountType.azienda,
        company_name="Cliente SRL",
        codice_fiscale="09876543210",
        partita_iva="09876543210",
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
def company_client(db_session: Session, company_user: User) -> Client:
    client = Client(
        company_id=company_user.id,
        client_type=ClientType.COMPANY,
        company_name="Demo S.r.l.",
        vat_number="12345678901",
        tax_code="01234567890",
        address="Via Roma 1",
        city="Milano",
        postal_code="20100",
        province="MI",
        country="IT",
        pec="demo@pec.it",
        recipient_code="ABC1234",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture()
def private_client(db_session: Session, company_user: User) -> Client:
    client = Client(
        company_id=company_user.id,
        client_type=ClientType.PRIVATE,
        first_name="Mario",
        last_name="Rossi",
        tax_code="RSSMRA80A01H501U",
        address="Via Verdi 1",
        city="Roma",
        postal_code="00100",
        province="RM",
        country="IT",
        recipient_code="0000000",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture()
def other_company_client(db_session: Session) -> Client:
    other_user = User(
        id=uuid4(),
        email="other@example.com",
        account_type=AccountType.azienda,
        company_name="Other SRL",
        codice_fiscale="11111111111",
        partita_iva="11111111111",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(other_user)
    db_session.flush()
    client = Client(
        company_id=other_user.id,
        client_type=ClientType.COMPANY,
        company_name="Hidden S.r.l.",
        vat_number="99999999999",
        tax_code="99999999999",
        address="Via Nascosta 1",
        city="Torino",
        postal_code="10100",
        province="TO",
        country="IT",
        recipient_code="ABC9999",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture()
def invoice_payload() -> dict[str, object]:
    return {
        "mode": 1,
        "invoiceNumber": "2026-001",
        "issueDate": "2026-05-15",
        "currency": "EUR",
        "documentType": "TD01",
        "paymentMethod": "MP05",
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


def test_create_invoice_persists_invoice_client_lines(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    invoice_payload: dict[str, object],
    company_user: User,
):
    payments_before = len(db_session.scalars(select(InvoicePayment)).all())

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["invoiceNumber"] == "2026-001"
    assert body["status"] == "DRAFT"
    assert body["client"]["clientType"] == "company"
    assert body["client"]["clientCode"] == "12345678901"
    assert body["lines"][0]["numberLine"] == 1
    assert body["vatSummary"][0]["vatRate"] in ("22.00", 22, 22.0)

    invoice = db_session.scalar(
        select(Invoice).where(
            Invoice.invoice_number == "2026-001",
            Invoice.company_id == company_user.id,
        )
    )
    assert invoice is not None
    assert invoice.customer_id is not None
    assert invoice.client_id == invoice.customer_id

    payments_after = len(db_session.scalars(select(InvoicePayment)).all())
    assert payments_after == payments_before + 1

    client_row = db_session.get(Client, invoice.customer_id)
    assert client_row is not None


def test_create_invoice_reuses_existing_customer_and_persists_customer_id(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    invoice_payload: dict[str, object],
    company_user: User,
):
    existing_client = Client(
        company_id=company_user.id,
        client_type=ClientType.COMPANY,
        company_name="Reusable Demo S.r.l.",
        vat_number="10987654321",
        tax_code="10987654321",
        address="Via Reuse 1",
        city="Bologna",
        postal_code="40100",
        province="MI",
        country="IT",
        pec="reusable@pec.it",
        recipient_code="0000000",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(existing_client)
    db_session.commit()
    db_session.refresh(existing_client)

    invoice_payload = dict(invoice_payload)
    invoice_payload["invoiceNumber"] = "2026-REUSE-001"
    client_payload = cast(dict[str, object], invoice_payload["client"])
    invoice_payload["client"] = dict(client_payload)
    client_payload = cast(dict[str, object], invoice_payload["client"])
    client_payload["companyName"] = "Reusable Demo S.r.l."
    client_payload["vatNumber"] = "10987654321"
    client_payload["taxCode"] = "10987654321"
    client_payload["address"] = "Via Reuse 1"
    client_payload["city"] = "Bologna"
    client_payload["postalCode"] = "40100"
    client_payload["province"] = "MI"
    client_payload["pec"] = "reusable@pec.it"

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    invoice = db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-REUSE-001"))
    assert invoice is not None
    assert invoice.customer_id == existing_client.id

    matching_clients = db_session.scalars(
        select(Client).where(Client.company_id == existing_client.company_id, Client.company_name == "Reusable Demo S.r.l.")
    ).all()
    assert len(matching_clients) == 1


def test_create_invoice_with_test_header_does_not_persist_db_changes(client: TestClient, auth_headers: dict[str, str], db_session: Session, invoice_payload: dict[str, object]):
    invoice_payload = dict(invoice_payload)
    invoice_payload["invoiceNumber"] = "2026-TEST-NO-PERSIST"

    response = client.post(
        "/invoices",
        json=invoice_payload,
        headers={**auth_headers, "Invoice-Form-Test": "true"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["invoiceNumber"] == "2026-TEST-NO-PERSIST"

    db_session.rollback()
    db_session.expire_all()

    assert db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-TEST-NO-PERSIST")) is None
    assert db_session.scalar(select(Client).where(Client.company_name == "Demo S.r.l.")) is None


def test_create_invoice_rejects_totals_mismatch(client: TestClient, auth_headers: dict[str, str], invoice_payload: dict[str, object]):
    invoice_payload = dict(invoice_payload)
    invoice_payload["total"] = 999

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 422


def test_get_clients_returns_user_clients(client: TestClient, auth_headers: dict[str, str], company_client: Client, private_client: Client):
    response = client.get("/invoices/clients", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert len(body["data"]) == 2
    assert {item["companyName"] or item["firstName"] for item in body["data"]} == {"Demo S.r.l.", "Mario"}


def test_get_clients_filters_by_query(client: TestClient, auth_headers: dict[str, str], company_client: Client, private_client: Client):
    response = client.get("/invoices/clients", params={"q": "demo"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["companyName"] == "Demo S.r.l."


def test_get_clients_only_returns_current_user_clients(client: TestClient, auth_headers: dict[str, str], company_client: Client, private_client: Client, other_company_client: Client):
    response = client.get("/invoices/clients", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert all(item["companyName"] != "Hidden S.r.l." for item in body["data"])
