from __future__ import annotations

import warnings
from datetime import datetime, timezone
from logging import getLogger
from typing import Generator
from uuid import UUID, uuid4

warnings.filterwarnings(
    "ignore",
    message=r"Please use `import python_multipart` instead\.",
    category=PendingDeprecationWarning,
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token
from app.config.settings import get_settings
from app.db.models.user import AccountType, User
from app.db.session import get_db
from app.main import app

logger = getLogger("uvicorn.error")
MOCK_PASSWORD = "AtlasFatturazione2025.."

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
)


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
def client(monkeypatch, db_session: Session) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("MOCKED_LOGIN_PASSWORD", MOCK_PASSWORD)
    monkeypatch.setenv("POSTGRES_CONNECTION_STRING", settings.database_url or "")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "1440")
    get_settings.cache_clear()

    logger.debug("Auth tests using database_url=%s", settings.database_url)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _create_user(db: Session, **kwargs) -> User:
    user = User(
        id=kwargs.get("id", uuid4()),
        email=kwargs.get("email", "mario@example.com"),
        account_type=kwargs.get("account_type", AccountType.privato),
        first_name=kwargs.get("first_name", "Mario"),
        last_name=kwargs.get("last_name", "Rossi"),
        company_name=kwargs.get("company_name"),
        codice_fiscale=kwargs.get("codice_fiscale", "RSSMRA80A01H501U"),
        partita_iva=kwargs.get("partita_iva"),
        phone=kwargs.get("phone", "+390612345678"),
        mobile=kwargs.get("mobile"),
        is_active=kwargs.get("is_active", True),
        is_verified=kwargs.get("is_verified", False),
        external_auth_provider=kwargs.get("external_auth_provider", "local"),
        external_auth_subject=kwargs.get("external_auth_subject"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    logger.debug("Creating auth test user email=%s id=%s", user.email, user.id)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture()
def patch_user_ids(monkeypatch):
    original_init = User.__init__

    def _init(self, **data):
        data.setdefault("id", uuid4())
        data.setdefault("created_at", datetime.now(timezone.utc))
        data.setdefault("updated_at", datetime.now(timezone.utc))
        original_init(self, **data)

    monkeypatch.setattr(User, "__init__", _init)


def test_register_login_me_flow(client: TestClient, patch_user_ids):
    logger.info("Starting auth flow test: register -> login -> me")

    response = client.post(
        "/auth/register",
        json={
            "accountType": "privato",
            "email": "mario@example.com",
            "password": "whatever123",
            "codiceFiscale": "RSSMRA80A01H501U",
            "partitaIva": None,
            "phone": "+390612345678",
            "mobile": None,
            "firstName": "Mario",
            "lastName": "Rossi",
            "nationality": None,
            "birthDate": None,
            "birthProvince": None,
            "birthComune": None,
            "companyName": None,
            "residenceCountry": None,
            "residenceProvince": None,
            "residenceComune": None,
            "residenceAddress": None,
            "residencePostal": None,
        },
    )

    logger.debug(
        "Register response status=%s body=%s",
        response.status_code,
        response.text,
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mario@example.com"

    login = client.post(
        "/auth/login",
        json={
            "email": "mario@example.com",
            "password": MOCK_PASSWORD,
        },
    )

    logger.debug(
        "Login response status=%s body=%s",
        login.status_code,
        login.text,
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    logger.debug(
        "/me response status=%s body=%s",
        me.status_code,
        me.text,
    )

    assert me.status_code == 200
    assert me.json()["email"] == "mario@example.com"


def test_login_invalid_credentials(client: TestClient, db_session: Session, patch_user_ids):
    _create_user(db_session, email="missing@example.com")

    response = client.post(
        "/auth/login",
        json={
            "email": "missing@example.com",
            "password": "wrong-password",
        },
    )

    logger.debug(
        "Invalid login response status=%s body=%s",
        response.status_code,
        response.text,
    )

    assert response.status_code == 401


def test_register_duplicate_email(client: TestClient, patch_user_ids):
    payload = {
        "accountType": "privato",
        "email": "dup@example.com",
        "password": "whatever123",
        "codiceFiscale": "RSSMRA80A01H501U",
        "partitaIva": None,
        "phone": None,
        "mobile": None,
        "firstName": "Mario",
        "lastName": "Rossi",
        "nationality": None,
        "birthDate": None,
        "birthProvince": None,
        "birthComune": None,
        "companyName": None,
        "residenceCountry": None,
        "residenceProvince": None,
        "residenceComune": None,
        "residenceAddress": None,
        "residencePostal": None,
    }

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)

    logger.debug(
        "Duplicate register statuses first=%s second=%s",
        first.status_code,
        second.status_code,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_me_rejects_expired_token(
    client: TestClient,
    db_session: Session,
    patch_user_ids,
):
    user = _create_user(
        db_session,
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        email="expired@example.com",
    )

    token = create_access_token(user.id, user.email, expires_minutes=-1)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    logger.debug(
        "Expired token /me response status=%s body=%s",
        response.status_code,
        response.text,
    )

    assert response.status_code == 401