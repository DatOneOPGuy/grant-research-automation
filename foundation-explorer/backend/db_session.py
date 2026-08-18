"""Postgres engine and session plumbing.

Deliberately unlike the read model's startup check. main_v5.py raises if
explorer_v5.db is missing, because without it the product has nothing to show.
Postgres is different: if it is unreachable the Explorer can still serve all 13
read routes, and crashlooping would take the whole site down to protect a
feature. So a failed connection degrades the account system and says so on
/api/health, and only the folder endpoints return 503.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import (
    DBAPIError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session, sessionmaker

import config

log = logging.getLogger(__name__)

_engine = None
_SessionLocal: sessionmaker[Session] | None = None

if config.DATABASE_URL:
    # pool_pre_ping because the droplet's Postgres may restart under us and a
    # stale pooled connection would surface as a 500 on the next save.
    _engine = create_engine(
        config.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5,
        future=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, future=True)
else:
    log.warning(
        "DATABASE_URL is not set: accounts and saved folders are disabled. "
        "The read model is unaffected.")


def configured() -> bool:
    return _SessionLocal is not None


def health() -> dict:
    """Connectivity probe for /api/health. Never raises."""
    if _engine is None:
        return {"status": "disabled", "detail": "DATABASE_URL is not set"}
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except SQLAlchemyError as exc:
        # The message can carry the host and user from the DSN, which is fine
        # for an operator on a gated hostname but not something to widen: the
        # password is masked by SQLAlchemy's own repr, not by us.
        log.error("Postgres health check failed: %s", exc)
        return {"status": "unreachable", "detail": type(exc).__name__}


UNAVAILABLE = "Saved folders are temporarily unavailable."


def get_db() -> Iterator[Session]:
    """FastAPI dependency. 503, never 500, when Postgres is not reachable.

    Two distinct failures both mean "the database is not there", and both must
    read as unavailable rather than as a bug in the endpoint:

      - DATABASE_URL unset, so there is no engine at all;
      - an engine that cannot connect, because Postgres is down or the DSN is
        wrong. SQLAlchemy connects lazily, so this surfaces on first use here
        rather than at startup.

    Only connection-level errors are translated. A failing query is still a
    500, because that is a bug and should look like one.
    """
    from fastapi import HTTPException

    if _SessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail=f"{UNAVAILABLE} No database is configured.")

    session = _SessionLocal()
    try:
        # Force the connection now so a dead server is caught here, where it
        # can be reported honestly, instead of mid-endpoint.
        session.execute(text("SELECT 1"))
    except (OperationalError, InterfaceError, DBAPIError) as exc:
        session.close()
        log.error("Postgres unreachable while serving a request: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"{UNAVAILABLE} The database is unreachable.") from exc

    try:
        yield session
    finally:
        session.close()
