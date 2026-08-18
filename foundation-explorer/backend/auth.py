"""Cloudflare Access identity.

Access sits in front of fcf.drakesdev.com, authenticates the user, and
forwards a signed JWT in Cf-Access-Jwt-Assertion on every request. We verify
that token against Cloudflare's JWKS and trust the email inside it. There are
no passwords, sessions, or reset flows here on purpose -- none of that is ours
to hold.

Fail closed everywhere: a missing, malformed, expired, wrong-audience or
wrong-issuer token is a 401. There is no anonymous fallback, because the
failure mode of a fallback is silent and permanent.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx
import jwt
from db_session import get_db
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient
from models_db import Team, User
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import config

log = logging.getLogger(__name__)

JWKS_TTL_SECONDS = 900  # 15 minutes
DEFAULT_TEAM_NAME = "Foundation Explorer"


class _JwksCache:
    """PyJWKClient with a TTL, plus a forced refresh on an unrecognised kid.

    Cloudflare rotates signing keys without warning. A pure TTL cache would
    reject every request for up to the TTL after a rotation, so an unknown kid
    triggers one immediate refetch before the token is judged invalid.
    """

    def __init__(self) -> None:
        self._client: PyJWKClient | None = None
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    @property
    def _url(self) -> str:
        return (f"https://{config.CF_ACCESS_TEAM_DOMAIN}"
                "/cdn-cgi/access/certs")

    def _build(self) -> PyJWKClient:
        # lifespan=0 so PyJWKClient's own cache never masks ours; this class
        # owns the refresh policy.
        return PyJWKClient(self._url, cache_keys=False, lifespan=0)

    def signing_key(self, token: str):
        with self._lock:
            expired = time.monotonic() - self._fetched_at > JWKS_TTL_SECONDS
            if self._client is None or expired:
                self._client = self._build()
                self._fetched_at = time.monotonic()
            client = self._client

        try:
            return client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError:
            # Unknown kid: refetch once in case the keys just rotated.
            with self._lock:
                self._client = self._build()
                self._fetched_at = time.monotonic()
                client = self._client
            return client.get_signing_key_from_jwt(token)


_jwks = _JwksCache()


def _unauthorised(reason: str) -> HTTPException:
    # The client is told only that it is unauthenticated. The reason goes to
    # the log, where an operator can see it and an attacker cannot.
    log.info("Access token rejected: %s", reason)
    return HTTPException(status_code=401, detail="Not authenticated")


def email_from_token(token: str) -> str:
    """Verify an Access JWT and return the email it asserts. Raises 401."""
    if not config.CF_CONFIGURED:
        raise _unauthorised("Cloudflare Access is not configured")
    try:
        key = _jwks.signing_key(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=config.CF_ACCESS_AUD,
            issuer=f"https://{config.CF_ACCESS_TEAM_DOMAIN}",
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    except (jwt.PyJWTError, httpx.HTTPError, OSError) as exc:
        raise _unauthorised(f"{type(exc).__name__}: {exc}") from exc

    # Service tokens carry no email. They are a different kind of principal
    # and this product has no use for one, so they are refused rather than
    # mapped onto some synthetic account.
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise _unauthorised("token carries no email claim")
    return email


def _default_team(db: Session) -> Team:
    """The single team every user joins today.

    Multi-tenancy is already expressed in the schema -- every folder query
    filters on team_id -- so adding a second team later is a data change, not
    a migration and not a rewrite of the authorisation rules.

    The team row is created by migration 0001 and is never created here. An
    earlier version fell back to creating one when the table was empty, which
    measured badly: eight concurrent first-logins against an empty table
    produced six teams and partitioned the users across them, so a colleague
    would log in to an empty list and nothing would report that anything was
    wrong. Silent data partitioning is the worst failure this system has, and
    a lazy create is a race by construction -- no amount of retry logic makes
    "check then insert" atomic across connections.

    So a missing team is now a refusal. It means the database was not migrated,
    or was restored from a dump that omitted the seed; both are deployment
    faults an operator must fix, and neither is improved by this process
    guessing.
    """
    team = db.scalars(select(Team).order_by(Team.id).limit(1)).first()
    if team is None:
        log.critical(
            "No team row exists. The database has not been migrated, or was "
            "restored without the seed from migration 0001. Refusing to "
            "create one: concurrent first-logins would each create their own "
            "and partition the team's saved folders. Run: alembic upgrade head"
        )
        raise HTTPException(
            status_code=503,
            detail="Accounts are not initialised on this server.")
    return team


def get_or_create_user(db: Session, email: str) -> User:
    """Resolve a verified email to a User row, creating it on first sight.

    No invite flow: Access already decided who is allowed through, and asking
    an admin to pre-register someone Cloudflare has just authenticated would
    be a second gate guarding nothing.
    """
    email = email.strip().lower()
    user = db.scalars(
        select(User).where(func.lower(User.email) == email)).first()
    if user is None:
        user = User(email=email, team_id=_default_team(db).id)
        db.add(user)
        try:
            db.commit()
        except SQLAlchemyError:
            # Two tabs hitting the API at once both see "no such user" and
            # both insert. The unique index makes one of them lose; that one
            # re-reads rather than 500s.
            db.rollback()
            user = db.scalars(
                select(User).where(func.lower(User.email) == email)).first()
            if user is None:
                raise
        else:
            log.info("Created account for %s", email)
            return user

    user.last_seen_at = func.now()
    db.commit()
    db.refresh(user)
    return user


def current_user(
    cf_access_jwt_assertion: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: the authenticated caller, or 401.

    FastAPI maps the parameter name to the Cf-Access-Jwt-Assertion header.
    """
    if config.DEV_USER_EMAIL:
        # Unreachable in any deployment that has Access in front of it:
        # config._validate() refuses to start the process if this is set
        # alongside either Cloudflare variable.
        return get_or_create_user(db, config.DEV_USER_EMAIL)

    if not cf_access_jwt_assertion:
        raise _unauthorised("no Cf-Access-Jwt-Assertion header")
    return get_or_create_user(db, email_from_token(cf_access_jwt_assertion))
