"""The real PyJWKClient, unstubbed.

Every other identity test replaces the key lookup with a stub, because what
they are testing is claim validation and team assignment. That stub turned out
to hide a fatal bug: auth.py constructed PyJWKClient with lifespan=0 to disable
PyJWT's own cache in favour of a hand-rolled one, and PyJWT rejects that value
at construction. Verification therefore raised before fetching a single key,
and because PyJWKClientError is a PyJWTError it was caught and returned as a
plain 401 -- indistinguishable from a wrong audience or a wrong issuer. It
reached production and could only be diagnosed from the droplet's logs.

So this file deliberately does the thing the others avoid: it builds the
client the application actually builds. No database and no Postgres are
needed, which means it runs everywhere the rest of the suite does.

The construction tests never touch the network, so a broken client fails
immediately and unconditionally. Only the last test talks to Cloudflare, and
it skips rather than fails when the network is unavailable -- a CI box without
egress should not turn into a red build, but a bad `lifespan` always should.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "foundation-explorer" / "backend"

jwt = pytest.importorskip("jwt")

TEAM_DOMAIN = "shy-thunder-37cd.cloudflareaccess.com"
EXPECTED_URL = f"https://{TEAM_DOMAIN}/cdn-cgi/access/certs"


@pytest.fixture()
def auth_mod(monkeypatch):
    """auth.py with production-shaped Access configuration and no database."""
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM_DOMAIN)
    monkeypatch.setenv("CF_ACCESS_AUD", "0" * 64)
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    for cached in ("config", "db_session", "models_db", "auth", "folders"):
        sys.modules.pop(cached, None)

    import auth

    yield auth

    for cached in ("config", "db_session", "models_db", "auth", "folders"):
        sys.modules.pop(cached, None)


# --- construction: never touches the network ---------------------------------

def test_the_real_client_can_be_constructed(auth_mod):
    """The regression test for the production outage.

    build_jwks_client() is what auth.py calls on the first verification. If its
    arguments are invalid, PyJWKClient raises here -- before any network I/O,
    before any token is examined -- and every login fails with a bare 401.
    """
    client = auth_mod.build_jwks_client()
    assert isinstance(client, jwt.PyJWKClient)


def test_the_jwk_set_cache_is_enabled_with_a_positive_lifespan(auth_mod):
    """lifespan must be > 0 or PyJWT refuses to construct the client at all."""
    assert auth_mod.JWKS_TTL_SECONDS > 0
    client = auth_mod.build_jwks_client()
    assert client.jwk_set_cache is not None, "the JWK set cache is disabled"
    assert client.jwk_set_cache.lifespan == auth_mod.JWKS_TTL_SECONDS


def test_lifespan_zero_is_what_broke_production(auth_mod):
    """Pin the failure mode so nobody reintroduces it as an optimisation.

    Passing lifespan=0 looks like "disable the cache". It is not: PyJWT treats
    it as invalid input and raises.
    """
    with pytest.raises(jwt.PyJWKClientError, match="Lifespan must be greater"):
        jwt.PyJWKClient(EXPECTED_URL, lifespan=0)


def test_per_key_lru_cache_stays_off(auth_mod):
    """Tier 2 caches by kid with no expiry, so a rotated-out key would stick.

    Tier 1 (the JWK set cache, with our TTL) is the one we want.
    """
    client = auth_mod.build_jwks_client()
    # lru_cache replaces the bound method when cache_keys=True.
    assert not hasattr(client.get_signing_key, "cache_info"), (
        "cache_keys is enabled; rotated keys would be cached indefinitely")


def test_client_targets_the_configured_team_domain(auth_mod):
    assert auth_mod.jwks_url() == EXPECTED_URL
    assert auth_mod.build_jwks_client().uri == EXPECTED_URL


def test_client_is_built_once_and_reused(auth_mod):
    """The TTL cache is worthless if a new client is built per request."""
    token_ish = "x.y.z"
    built: list[int] = []
    real = auth_mod.build_jwks_client

    def counting():
        built.append(1)
        client = real()
        client.get_signing_key_from_jwt = lambda _t: "key"
        return client

    auth_mod.build_jwks_client = counting
    auth_mod._jwks_client = None
    try:
        for _ in range(5):
            auth_mod._signing_key(token_ish)
    finally:
        auth_mod.build_jwks_client = real
        auth_mod._jwks_client = None
    assert len(built) == 1, f"built the client {len(built)} times"


# --- live endpoint -----------------------------------------------------------

@pytest.mark.skipif(os.environ.get("NO_NETWORK_TESTS") == "1",
                    reason="NO_NETWORK_TESTS=1")
def test_real_keys_come_back_from_cloudflare(auth_mod):
    """Fetch the live JWK set through the real client.

    Proves the URL resolves and returns usable signing keys, rather than a
    404 page that happens to parse. Skips on a transport failure so an offline
    CI box does not fail the build; a malformed response still fails.
    """
    client = auth_mod.build_jwks_client()
    try:
        keys = client.get_signing_keys()
    except jwt.PyJWKClientConnectionError as exc:
        pytest.skip(f"cannot reach the JWKS endpoint: {exc}")

    assert keys, "the endpoint returned no signing keys"
    for key in keys:
        assert key.key_id, "a key has no kid, so no token could match it"
        assert key.public_key_use in ("sig", None)
        # A 404 page parsed as JSON would not survive this.
        assert key.key is not None
