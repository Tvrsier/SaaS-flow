from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, decode_access_token
from app.config.settings import get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.modules.auth.schemas import AuthLoginResponse, AuthMeResponse, AuthRegisterResponse
from app.schemas.user import UserCreate, UserLogin, UserRead

logger = getLogger("uvicorn.error")

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def _me_payload(user: User) -> AuthMeResponse:
    logger.debug("Building /auth/me payload for email=%s", user.email)
    return AuthMeResponse(
        name=user.first_name or user.company_name,
        surname=user.last_name,
        email=user.email,
        companyName=user.company_name,
        partitaIva=user.partita_iva,
        codiceFiscale=user.codice_fiscale,
        phone=user.phone,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    logger.debug("Resolving current user from bearer token present=%s", credentials is not None)
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Missing or invalid auth scheme for /auth/me")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    logger.debug("Bearer token received on /auth/me len=%s", len(credentials.credentials))
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        logger.warning("Invalid auth token received on /auth/me")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    subject = payload.get("sub")
    exp_raw = payload.get("exp")
    logger.debug("JWT payload subject=%s exp=%s", subject, exp_raw)
    if not subject:
        logger.warning("JWT payload missing subject")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        user_id = UUID(str(subject))
    except ValueError:
        logger.warning("JWT subject is not a valid UUID/email-token subject: %s", subject)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if exp_raw is None:
        logger.warning("JWT payload missing exp")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if datetime.fromtimestamp(int(exp_raw), tz=timezone.utc) <= datetime.now(timezone.utc):
        logger.warning("Expired auth token received on /auth/me exp=%s now=%s", exp_raw, datetime.now(timezone.utc).isoformat())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user: User | None = db.get(User, user_id)
    logger.debug("User lookup by id=%s found=%s", user_id, user is not None)
    if user is None or not user.is_active:
        logger.warning("Active user not found for token subject=%s", subject)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


@router.post("/register", response_model=AuthRegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    logger.info("Register request received email=%s account_type=%s", payload.email, payload.account_type)
    existing = db.scalar(select(User).where(User.email == payload.email))
    logger.debug("Register existing user lookup email=%s found=%s", payload.email, existing is not None)
    if existing is not None:
        logger.warning("Register duplicate email rejected email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = User(
        email=str(payload.email),
        account_type=payload.account_type,
        first_name=payload.first_name,
        last_name=payload.last_name,
        company_name=payload.company_name,
        codice_fiscale=payload.codice_fiscale,
        partita_iva=payload.partita_iva,
        phone=payload.phone,
        mobile=payload.mobile,
        is_active=True,
        is_verified=False,
    )
    logger.debug("Register created transient user email=%s", user.email)
    db.add(user)
    try:
        db.commit()
        logger.info("Register committed email=%s id=%s", user.email, user.id)
    except IntegrityError:
        db.rollback()
        logger.exception("Register commit failed for email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    db.refresh(user)
    logger.debug("Register refreshed user email=%s id=%s", user.email, user.id)
    token = create_access_token(user.email)
    logger.info("Register token issued email=%s", user.email)
    return {"access_token": token, "user": UserRead.model_validate(user)}


@router.post("/login", response_model=AuthLoginResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    settings = get_settings()
    logger.info("Login request received email=%s", payload.email)
    user = db.scalar(select(User).where(User.email == payload.email))
    logger.debug("Login user lookup email=%s found=%s", payload.email, user is not None)
    if user is None or not user.is_active:
        logger.warning("Login failed because user missing or inactive email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.debug(
        "Comparing login password with mock password loaded from settings len=%s configured=%s",
        len(settings.mock_login_password or ""),
        settings.mock_login_password is not None,
    )
    if payload.password != settings.mock_login_password:
        logger.warning("Login attempt with invalid mock password for %s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    try:
        db.commit()
        logger.info("Login commit succeeded email=%s id=%s", user.email, user.id)
    except IntegrityError:
        db.rollback()
        logger.exception("Login commit failed email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    db.refresh(user)
    logger.debug("Login refreshed user email=%s last_login_at=%s", user.email, user.last_login_at)
    token = create_access_token(user.email)
    logger.info("Login token issued email=%s", user.email)
    return {"access_token": token, "user": UserRead.model_validate(user)}


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user)) -> AuthMeResponse:
    logger.info("/auth/me success email=%s", current_user.email)
    return _me_payload(current_user)
