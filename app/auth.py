from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.config.settings import get_settings
from app.logger import logger
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    logger.debug("Hashing password")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    logger.debug("Verifying password against stored hash")
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: UUID,
    email: str,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expires_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    logger.debug("Creating JWT access token payload=%s", {**payload, "sub": str(subject), "exp": payload["exp"]})
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    logger.info("JWT access token created for subject=%s exp=%s", subject, payload["exp"])
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    logger.debug("Decoding JWT token (len=%s)", len(token))
    payload: dict[str, Any] = {}
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning("User token is expired")
    except jwt.InvalidSignatureError:
        logger.warning("User token is invalid")
    except Exception:
        logger.exception("JWT decode failed")
        raise
    logger.debug("JWT decoded successfully subject=%s exp=%s", payload.get("sub"), payload.get("exp"))
    return payload
