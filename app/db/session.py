from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings

DB_CONNECT_TIMEOUT_SECONDS = 30
DB_STATEMENT_TIMEOUT_MS = 30_000


def _build_database_url(database_url: str):
    url = make_url(database_url)
    query = dict(url.query)
    query.setdefault("connect_timeout", str(DB_CONNECT_TIMEOUT_SECONDS))
    query.setdefault("options", f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}")
    return url.set(query=query)


settings = get_settings()
engine = create_engine(_build_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
