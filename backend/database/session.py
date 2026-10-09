"""Database engine, session factory and the FastAPI dependency."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def _engine_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"echo": settings.db_echo, "future": True}
    if settings.is_sqlite:
        # SQLite's default same-thread check breaks FastAPI's threadpool.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Recycle before typical cloud idle timeouts and verify connections
        # so a dropped socket surfaces as a retry rather than a 500.
        kwargs.update(pool_pre_ping=True, pool_recycle=1800, pool_size=10, max_overflow=20)
    return kwargs


engine = create_engine(settings.database_url, **_engine_kwargs())

if settings.is_sqlite:
    logger.warning(
        "Running on SQLite (%s). This is a development fallback only -- "
        "AyuDrishti targets PostgreSQL. Set DATABASE_URL to a postgresql+psycopg2 "
        "URL for anything beyond local testing.",
        settings.database_url,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
        # Foreign keys are off by default in SQLite, which would let the
        # dev database accept rows PostgreSQL would reject.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
