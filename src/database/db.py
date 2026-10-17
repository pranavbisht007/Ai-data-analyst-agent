"""src/database/db.py — Engine creation and session factory."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATABASE_URL
from src.database.models import Base

logger = logging.getLogger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite only; safe with sessionmaker
    echo=False,
    pool_pre_ping=True,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    """Enable WAL mode and foreign-key enforcement for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


_SessionFactory = sessionmaker(
    bind=_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ── Public API ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables (idempotent). Call once at startup."""
    Base.metadata.create_all(_engine)
    logger.info("Database initialised: %s", DATABASE_URL.split("///")[-1])


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional session; roll back on exception."""
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_version() -> str:
    """Return the SQLite library version string."""
    with _engine.connect() as conn:
        row = conn.execute(text("SELECT sqlite_version()")).fetchone()
        return row[0] if row else "unknown"
