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

# TTL for the cached JWK set, in seconds. PyJWKClient requires this to be
# strictly positive and raises PyJWKClientError at construction otherwise.
JWKS_TTL_SECONDS = 900  # 15 minutes
JWKS_TIMEOUT_SECONDS = 10
DEFAULT_TEAM_NAME = "Foundation Explorer"


def jwks_url() -> str:
    return f"https://{config.CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs"


def build_jwks_client() -> PyJWKClient:
    """Construct the JWKS client. Separated so a test can call it directly.

    PyJWKClient already provides everything this module needs, and an earlier
    version of this file reimplemented all of it badly:

      - a TTL cache of the JWK set. PyJWKClient's tier-1 cache does this via
        `lifespan`, which must be a positive number of seconds.
      - a refetch when a token's kid is not in the cached set. PyJWKClient's
        get_signing_key already refreshes and retries once on a kid miss, so
        a key rotation is handled without waiting out the TTL.

    The hand-rolled version passed lifespan=0 to disable PyJWT's cache and let
    the wrapper own the policy. PyJWT rejects that value at construction, so
    every verification raised before a single key was fetched -- which in
    production meant a blanket 401 that looked exactly like a bad audience or
    a bad issuer. The local tests never caught it because they stubbed the
    key lookup, which is precisely the seam where the bug lived.

    cache_keys is left at its default of False on purpose. That tier-2 LRU
    caches keys by kid with no expiry at all, so a key Cloudflare has rotated
    out would be retained indefinitely.
    """
    return PyJWKClient(
        jwks_url(),
        lifespan=JWKS_TTL_SECONDS,
        timeout=JWKS_TIMEOUT_SECONDS,
    )


_jwks_client: PyJWKClient | None = None
_jwks_lock = threading.Lock()


def _signing_key(token: str):
    """The signing key for this token, from a lazily built shared client.

    Built on first use rather than at import: the team domain is not known at
    import time in dev-bypass mode, and a module that constructs network
    clients on import is harder to test than one that does not.
    """
    global _jwks_client
    client = _jwks_client
    if client is None:
        with _jwks_lock:
            if _jwks_client is None:
                _jwks_client = build_jwks_client()
            client = _jwks_client
    return client.get_signing_key_from_jwt(token)


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
        key = _signing_key(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=config.CF_ACCESS_AUD,
            issuer=f"https://{config.CF_ACCESS_TEAM_DOMAIN}",
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    # PyJWKClient fetches with urllib, and wraps transport failures in
    # PyJWKClientConnectionError, which is itself a PyJWTError -- so the JWKS
    # and verification failures both land here. OSError is belt and braces for
    # a socket error that escapes that wrapping.
    except (jwt.PyJWTError, OSError) as exc:
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
