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
from app.db.models.invoice import Client, Invoice, InvoiceDocument, InvoicePayment, InvoicePaymentDetails, VatMovement  # noqa: E402
from app.db.models.user import AccountType, User, UserPaymentProfile  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.invoices.domain.enums import ClientType, PaymentMethod  # noqa: E402

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
        "paymentDetails": {
            "beneficiary": "GestPro SRL",
            "iban": "IT60X0542811101000000123456",
        },
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
    assert body["paymentDetails"]["beneficiary"] == "GestPro SRL"
    assert body["paymentDetails"]["iban"] == "IT60X0542811101000000123456"

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
    payment_details = db_session.get(InvoicePaymentDetails, invoice.id)
    assert payment_details is not None
    assert payment_details.beneficiary == "GestPro SRL"
    assert payment_details.iban == "IT60X0542811101000000123456"

    client_row = db_session.get(Client, invoice.customer_id)
    assert client_row is not None

    vat_movements = db_session.scalars(
        select(VatMovement).where(
            VatMovement.source_type == "ACTIVE_INVOICE",
            VatMovement.source_invoice_id == invoice.id,
        )
    ).all()
    assert len(vat_movements) == 1
    assert vat_movements[0].movement_type == "DEBIT"
    assert vat_movements[0].vat_amount == invoice.vat_amount


def test_create_invoice_save_payment_profile_creates_profile(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    invoice_payload: dict[str, object],
    company_user: User,
):
    payload = dict(invoice_payload)
    payload["invoiceNumber"] = "2026-001-PROFILE"
    payload["savePaymentProfile"] = True

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 201
    profile = db_session.scalar(
        select(UserPaymentProfile).where(
            UserPaymentProfile.user_id == company_user.id,
            UserPaymentProfile.payment_method == PaymentMethod.MP05,
        )
    )
    assert profile is not None
    assert profile.beneficiary == "GestPro SRL"
    assert profile.iban == "IT60X0542811101000000123456"


def test_create_invoice_save_payment_profile_updates_existing_profile(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    invoice_payload: dict[str, object],
    company_user: User,
):
    profile = UserPaymentProfile(
        user_id=company_user.id,
        payment_method=PaymentMethod.MP05,
        beneficiary="Old Beneficiary",
        iban="IT60X0000000000000000000000",
    )
    db_session.add(profile)
    db_session.commit()

    payload = dict(invoice_payload)
    payload["invoiceNumber"] = "2026-001-PROFILE-UPD"
    payload["savePaymentProfile"] = True
    payload["paymentDetails"] = {
        "beneficiary": "Nuovo Beneficiario",
        "iban": "IT60X0542811101000000123999",
        "bic": "ABCDEF12",
    }

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 201
    stored_profiles = db_session.scalars(
        select(UserPaymentProfile).where(
            UserPaymentProfile.user_id == company_user.id,
            UserPaymentProfile.payment_method == PaymentMethod.MP05,
        )
    ).all()
    assert len(stored_profiles) == 1
    assert stored_profiles[0].beneficiary == "Nuovo Beneficiario"
    assert stored_profiles[0].iban == "IT60X0542811101000000123999"
    assert stored_profiles[0].bic == "ABCDEF12"


def test_create_invoice_split_payment_does_not_create_vat_debit_movements(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    invoice_payload: dict[str, object],
    company_user: User,
):
    payload = dict(invoice_payload)
    payload["invoiceNumber"] = "2026-SPLIT-001"
    payload["esigibilitaIva"] = "S"

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 201
    invoice = db_session.scalar(
        select(Invoice).where(
            Invoice.invoice_number == "2026-SPLIT-001",
            Invoice.company_id == company_user.id,
        )
    )
    assert invoice is not None

    vat_movements = db_session.scalars(
        select(VatMovement).where(
            VatMovement.source_type == "ACTIVE_INVOICE",
            VatMovement.source_invoice_id == invoice.id,
        )
    ).all()
    assert vat_movements == []


def test_create_invoice_mp05_without_payment_details_returns_422(
    client: TestClient,
    auth_headers: dict[str, str],
    invoice_payload: dict[str, object],
):
    payload = dict(invoice_payload)
    payload.pop("paymentDetails", None)

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_invoice_mp05_without_iban_returns_422(
    client: TestClient,
    auth_headers: dict[str, str],
    invoice_payload: dict[str, object],
):
    payload = dict(invoice_payload)
    payload["paymentDetails"] = {"beneficiary": "GestPro SRL"}

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_invoice_mp01_with_null_payment_details_succeeds(
    client: TestClient,
    auth_headers: dict[str, str],
    invoice_payload: dict[str, object],
):
    payload = dict(invoice_payload)
    payload["paymentMethod"] = "MP01"
    payload["paymentDetails"] = None

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["paymentDetails"] is None


def test_create_invoice_mp01_with_payment_details_returns_422(
    client: TestClient,
    auth_headers: dict[str, str],
    invoice_payload: dict[str, object],
):
    payload = dict(invoice_payload)
    payload["paymentMethod"] = "MP01"
    payload["paymentDetails"] = {"paymentCode": "ABC123"}

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_create_invoice_mp23_requires_payment_code(
    client: TestClient,
    auth_headers: dict[str, str],
    invoice_payload: dict[str, object],
):
    payload = dict(invoice_payload)
    payload["paymentMethod"] = "MP23"
    payload["paymentDetails"] = {"beneficiary": "GestPro SRL"}

    response = client.post("/invoices", json=payload, headers=auth_headers)

    assert response.status_code == 422


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


def test_create_invoice_persists_documents_and_attachments(client: TestClient, auth_headers: dict[str, str], db_session: Session, invoice_payload: dict[str, object], company_user: User):
    invoice_payload = dict(invoice_payload)
    invoice_payload["invoiceNumber"] = "2026-DOC-001"
    invoice_payload["attachments"] = [
        {
            "fileName": "allegato.pdf",
            "mimeType": "application/pdf",
            "contentBase64": "UERG",
            "size": 3,
            "description": "Allegato di supporto",
        }
    ]
    invoice_payload["documents"] = [
        {
            "file": {
                "fileName": "ordine.pdf",
                "mimeType": "application/pdf",
                "contentBase64": "UERG",
                "size": 3,
            },
            "relatedDocumentType": "DatiOrdineAcquisto",
            "idDocumento": "ORD-001",
            "riferimentoNumeroLinea": [1, 2],
            "data": "2026-05-10",
            "codiceCIG": "Z123456789",
        },
        {
            "file": {
                "fileName": "nota.pdf",
                "mimeType": "application/pdf",
                "contentBase64": "UERG",
                "size": 3,
                "description": "Nota allegata",
            },
        },
    ]

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    invoice = db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-DOC-001", Invoice.company_id == company_user.id))
    assert invoice is not None

    stored_documents = db_session.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice.id)).all()
    assert len(stored_documents) == 3
    assert {doc.xml_block for doc in stored_documents} == {"ALLEGATI", "DatiOrdineAcquisto"}
    assert any(doc.description == "Allegato di supporto" for doc in stored_documents)
    assert any(doc.document_number == "ORD-001" for doc in stored_documents)
    assert any(doc.reference_line_numbers == [1, 2] for doc in stored_documents)
    assert any(doc.filename == "ordine.pdf" for doc in stored_documents)
    assert any(doc.filename == "nota.pdf" for doc in stored_documents)
    assert any(doc.xml_block == "ALLEGATI" and doc.include_in_xml is False for doc in stored_documents)


def test_create_invoice_deduplicates_same_file_in_attachments_and_documents(client: TestClient, auth_headers: dict[str, str], db_session: Session, invoice_payload: dict[str, object], company_user: User):
    invoice_payload = dict(invoice_payload)
    invoice_payload["invoiceNumber"] = "2026-ATT-001"
    invoice_payload["attachments"] = [
        {
            "fileName": "solo-allegato.txt",
            "mimeType": "text/plain",
            "contentBase64": "QUJD",
            "size": 3,
            "description": "Allegato senza metadati SDI",
        }
    ]
    invoice_payload["documents"] = [
        {
            "file": {
                "fileName": "solo-allegato.txt",
                "mimeType": "text/plain",
                "contentBase64": "QUJD",
                "size": 3,
                "description": "Allegato senza metadati SDI",
            }
        }
    ]

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    invoice = db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-ATT-001", Invoice.company_id == company_user.id))
    assert invoice is not None

    stored_documents = db_session.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice.id)).all()
    assert len(stored_documents) == 1
    stored_document = stored_documents[0]
    assert stored_document.xml_block == "ALLEGATI"
    assert stored_document.include_in_xml is False
    assert stored_document.filename == "solo-allegato.txt"

    body = response.json()
    assert len(body["attachments"]) == 1
    assert body["documents"] == []


def test_create_invoice_prefers_related_document_over_attachment_for_same_file(client: TestClient, auth_headers: dict[str, str], db_session: Session, invoice_payload: dict[str, object], company_user: User):
    invoice_payload = dict(invoice_payload)
    invoice_payload["invoiceNumber"] = "2026-REL-001"
    invoice_payload["attachments"] = [
        {
            "fileName": "ordine.pdf",
            "mimeType": "application/pdf",
            "contentBase64": "UERG",
            "size": 3,
            "description": "Duplicato da attachments",
        }
    ]
    invoice_payload["documents"] = [
        {
            "file": {
                "fileName": "ordine.pdf",
                "mimeType": "application/pdf",
                "contentBase64": "UERG",
                "size": 3,
                "description": "Documento con metadata SDI",
            },
            "relatedDocumentType": "DatiOrdineAcquisto",
            "idDocumento": "ORD-002",
            "riferimentoNumeroLinea": [1],
            "data": "2026-05-11",
            "codiceCIG": "Z123456780",
        }
    ]

    response = client.post("/invoices", json=invoice_payload, headers=auth_headers)

    assert response.status_code == 201
    invoice = db_session.scalar(select(Invoice).where(Invoice.invoice_number == "2026-REL-001", Invoice.company_id == company_user.id))
    assert invoice is not None

    stored_documents = db_session.scalars(select(InvoiceDocument).where(InvoiceDocument.invoice_id == invoice.id)).all()
    assert len(stored_documents) == 1
    stored_document = stored_documents[0]
    assert stored_document.xml_block == "DatiOrdineAcquisto"
    assert stored_document.include_in_xml is True
    assert stored_document.filename == "ordine.pdf"
    assert stored_document.document_number == "ORD-002"
    assert stored_document.reference_line_numbers == [1]

    body = response.json()
    assert body["attachments"] == []
    assert len(body["documents"]) == 1
    assert body["documents"][0]["relatedDocumentType"] == "DatiOrdineAcquisto"
    assert body["documents"][0]["includedInXml"] is True


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


def test_get_invoices_last_invoice_number_follows_created_at(client: TestClient, auth_headers: dict[str, str], invoice_payload: dict[str, object]):
    first_payload = dict(invoice_payload)
    first_payload["invoiceNumber"] = "2026-100"
    first_payload["issueDate"] = "2026-05-01"

    second_payload = dict(invoice_payload)
    second_payload["invoiceNumber"] = "2026-011"
    second_payload["issueDate"] = "2026-06-11"

    third_payload = dict(invoice_payload)
    third_payload["invoiceNumber"] = "2026-200"
    third_payload["issueDate"] = "2026-05-15"

    assert client.post("/invoices", json=first_payload, headers=auth_headers).status_code == 201
    assert client.post("/invoices", json=second_payload, headers=auth_headers).status_code == 201
    assert client.post("/invoices", json=third_payload, headers=auth_headers).status_code == 201

    response = client.get("/invoices", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["lastInvoiceNumber"] == "2026-200"


def test_create_invoice_with_ddt_stores_in_metadata(client: TestClient, db_session: Session, auth_headers: dict[str, str], invoice_payload: dict[str, object]):
    payload_with_ddt = dict(invoice_payload)
    payload_with_ddt["ddt"] = [
        {
            "numeroDDT": "DDT-2026-001",
            "dataDDT": "2026-05-10",
            "riferimentoNumeroLinea": [1],
        },
        {
            "numeroDDT": "DDT-2026-002",
            "dataDDT": "2026-05-11",
            "riferimentoNumeroLinea": [1, 2],
        },
    ]

    response = client.post("/invoices", json=payload_with_ddt, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    invoice_id = body["id"]

    persisted = db_session.get(Invoice, invoice_id)
    assert persisted is not None
    assert persisted.invoice_metadata is not None
    assert "ddt" in persisted.invoice_metadata
    assert len(persisted.invoice_metadata["ddt"]) == 2
    assert persisted.invoice_metadata["ddt"][0]["numero"] == "DDT-2026-001"
    assert persisted.invoice_metadata["ddt"][0]["data"] == "2026-05-10"
    assert persisted.invoice_metadata["ddt"][0]["riferimento_linee"] == [1]
    assert persisted.invoice_metadata["ddt"][1]["numero"] == "DDT-2026-002"
    assert persisted.invoice_metadata["ddt"][1]["data"] == "2026-05-11"
    assert persisted.invoice_metadata["ddt"][1]["riferimento_linee"] == [1, 2]
