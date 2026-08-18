"""Runtime configuration for the account system, read from the environment.

No defaults for the Cloudflare Access settings. A missing value means the
deployment is misconfigured, and the right response is to say so rather than
to fall back to something that happens to boot.

The read path (explorer_v5.db) deliberately does not appear here: it is
configured by v5.DB_PATH and stays untouched by any of this.
"""

from __future__ import annotations

import os


class ConfigError(RuntimeError):
    """Raised at import time when the environment cannot be trusted."""


def _clean(name: str) -> str | None:
    value = (os.environ.get(name) or "").strip()
    return value or None


# Cloudflare Access. Both are required together in a real deployment: the team
# domain identifies the JWKS endpoint and the issuer, the aud tag pins the
# token to this application specifically.
CF_ACCESS_TEAM_DOMAIN = _clean("CF_ACCESS_TEAM_DOMAIN")
CF_ACCESS_AUD = _clean("CF_ACCESS_AUD")

# Postgres for accounts and shared folders. Absent means the account features
# are unavailable, which /api/health reports as degraded -- it is not a reason
# to refuse to serve the read model.
DATABASE_URL = _clean("DATABASE_URL")

# Local development without Cloudflare in front. See _validate(): this is only
# honoured when no Cloudflare configuration is present at all.
DEV_USER_EMAIL = _clean("DEV_USER_EMAIL")

CF_CONFIGURED = bool(CF_ACCESS_TEAM_DOMAIN and CF_ACCESS_AUD)


def _validate() -> None:
    """Fail at startup on any environment that is ambiguous about identity.

    The dev bypass mints a session for DEV_USER_EMAIL without checking a
    token. That is fine on a laptop and catastrophic behind a public
    hostname, so the two configurations are made mutually exclusive at boot
    rather than resolved by precedence at request time: a precedence rule
    still runs, and a rule that runs can be reasoned about wrongly.

    Refusing to start is the point. A crash on deploy is loud; a server that
    quietly accepts an unauthenticated header is not.
    """
    if DEV_USER_EMAIL and (CF_ACCESS_TEAM_DOMAIN or CF_ACCESS_AUD):
        raise ConfigError(
            "DEV_USER_EMAIL is set alongside Cloudflare Access configuration "
            "(CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD). The dev bypass issues "
            "sessions without verifying a token and must never be reachable "
            "in a deployment that has Access in front of it. Unset "
            "DEV_USER_EMAIL, or unset both Cloudflare variables."
        )
    if CF_ACCESS_TEAM_DOMAIN and not CF_ACCESS_AUD:
        raise ConfigError(
            "CF_ACCESS_TEAM_DOMAIN is set but CF_ACCESS_AUD is not. Without "
            "the audience tag every Access token issued by the team domain "
            "would be accepted, including ones minted for other applications."
        )
    if CF_ACCESS_AUD and not CF_ACCESS_TEAM_DOMAIN:
        raise ConfigError(
            "CF_ACCESS_AUD is set but CF_ACCESS_TEAM_DOMAIN is not. There is "
            "no JWKS endpoint or issuer to verify tokens against."
        )


_validate()


def auth_mode() -> str:
    """One of 'cloudflare', 'dev-bypass', 'unconfigured'. For /api/health."""
    if CF_CONFIGURED:
        return "cloudflare"
    if DEV_USER_EMAIL:
        return "dev-bypass"
    return "unconfigured"
