"""End-to-end identity: real JWTs through the real auth path.

test_folders_api.py overrides the current_user dependency, which is right for
testing authorisation but means the token path itself is never exercised. This
file does the opposite: it mints genuine RS256 tokens, signs them with a key
the JWKS cache is pointed at, and lets auth.current_user verify them. Nothing
here is stubbed except where the public keys come from.

What that buys, specifically:

  - the issuer string auth.py pins is checked against a token, so a format
    mismatch fails here rather than 401ing every request in production;
  - two DIFFERENT emails arriving on two DIFFERENT tokens are proven to land
    in the same team and see the same folders -- the sharing guarantee the
    whole feature rests on;
  - attribution is proven to survive that sharing.

The signing key is generated locally. The values pinned as issuer/audience are
the live ones for shy-thunder-37cd, so the strings under test are the strings
in production.

    TEST_DATABASE_URL=postgresql+psycopg://localhost/fcf_test \
        pytest tests/test_access_identity.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "foundation-explorer" / "backend"

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)

jwt = pytest.importorskip("jwt")
pytest.importorskip("sqlalchemy")

from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

# The live team domain and its issuer, confirmed against
# https://shy-thunder-37cd.cloudflareaccess.com/.well-known/openid-configuration
TEAM_DOMAIN = "shy-thunder-37cd.cloudflareaccess.com"
ISSUER = f"https://{TEAM_DOMAIN}"
AUD = "0" * 64  # shape of a real AUD tag; the live value is not needed here


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def env(signing_key):
    """Import the backend configured exactly as production is.

    Cloudflare variables set, DEV_USER_EMAIL absent -- the combination
    config.py permits and the droplet actually runs.
    """
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["CF_ACCESS_TEAM_DOMAIN"] = TEAM_DOMAIN
    os.environ["CF_ACCESS_AUD"] = AUD
    os.environ.pop("DEV_USER_EMAIL", None)
    sys.path.insert(0, str(BACKEND))
    for cached in ("config", "db_session", "models_db", "auth", "folders"):
        sys.modules.pop(cached, None)

    import auth
    import db_session
    import folders as folders_mod
    import sqlalchemy
    from models_db import Base

    try:
        Base.metadata.drop_all(db_session._engine)
        Base.metadata.create_all(db_session._engine)
    except sqlalchemy.exc.SQLAlchemyError as exc:
        pytest.skip(f"Postgres unreachable: {exc}")

    # Point the JWKS cache at our key instead of Cloudflare's endpoint. This is
    # the only stub: verification, issuer, audience and expiry are all real.
    class _Key:
        key = signing_key.public_key()

    class _Stub:
        def signing_key(self, token):
            return _Key()

    auth._jwks = _Stub()

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(folders_mod.router)
    return app, db_session, auth


def token_for(signing_key, email: str, **overrides) -> str:
    claims = {
        "email": email,
        "iss": ISSUER,
        "aud": AUD,
        "iat": int(time.time()) - 5,
        "exp": int(time.time()) + 600,
        "sub": f"sub-{email}",
    }
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="RS256")


def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def hdr(token: str, name: str = "Cf-Access-Jwt-Assertion") -> dict:
    return {name: token}


@pytest.fixture()
def clean(env):
    _, db_session, _ = env
    from models_db import Folder, FolderItem, Team, User

    session = db_session._SessionLocal()
    session.query(FolderItem).delete()
    session.query(Folder).delete()
    session.query(User).delete()
    session.query(Team).delete()
    # Seed the team the way migration 0001 does. create_all does not run the
    # migration's INSERT, and the application no longer creates a team on
    # demand -- deliberately, see _default_team -- so a fixture that skipped
    # this would be testing an unmigrated database.
    session.add(Team(name="Foundation Explorer"))
    session.commit()
    session.close()


@pytest.fixture()
def no_team(env):
    """An unmigrated (or badly restored) database: tables but no team row."""
    _, db_session, _ = env
    from models_db import Folder, FolderItem, Team, User

    session = db_session._SessionLocal()
    session.query(FolderItem).delete()
    session.query(Folder).delete()
    session.query(User).delete()
    session.query(Team).delete()
    session.commit()
    session.close()


# --- 1. issuer format --------------------------------------------------------

def test_live_issuer_string_is_accepted(env, clean, signing_key):
    """The pinned issuer matches what this team domain actually asserts."""
    app, _, _ = env
    token = token_for(signing_key, "issuer-check@example.com")
    with client(app) as c:
        response = c.get("/api/v5/me", headers=hdr(token))
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "issuer-check@example.com"


@pytest.mark.parametrize("bad_iss", [
    f"https://{TEAM_DOMAIN}/",           # trailing slash
    TEAM_DOMAIN,                          # no scheme
    "https://other-team.cloudflareaccess.com",
])
def test_wrong_issuer_is_rejected(env, clean, signing_key, bad_iss):
    """The issuer pin is load-bearing, not decorative."""
    app, _, _ = env
    token = token_for(signing_key, "a@example.com", iss=bad_iss)
    with client(app) as c:
        assert c.get("/api/v5/me", headers=hdr(token)).status_code == 401


def test_wrong_audience_is_rejected(env, clean, signing_key):
    app, _, _ = env
    token = token_for(signing_key, "a@example.com", aud="1" * 64)
    with client(app) as c:
        assert c.get("/api/v5/me", headers=hdr(token)).status_code == 401


def test_expired_token_is_rejected(env, clean, signing_key):
    app, _, _ = env
    token = token_for(signing_key, "a@example.com",
                      exp=int(time.time()) - 60, iat=int(time.time()) - 600)
    with client(app) as c:
        assert c.get("/api/v5/me", headers=hdr(token)).status_code == 401


def test_token_without_email_is_rejected(env, clean, signing_key):
    """A service token has no email and must not become an account."""
    app, _, _ = env
    claims = {
        "iss": ISSUER, "aud": AUD, "sub": "service-token",
        "iat": int(time.time()) - 5, "exp": int(time.time()) + 600,
    }
    token = jwt.encode(claims, signing_key, algorithm="RS256")
    with client(app) as c:
        assert c.get("/api/v5/me", headers=hdr(token)).status_code == 401


# --- 3. THE SHARING CLAIM ----------------------------------------------------

def test_two_distinct_tokens_land_in_one_team_and_share_everything(
        env, clean, signing_key):
    """Emily and her colleague see the same list.

    Two different emails, two independently minted valid tokens, two separate
    get-or-creates. Neither user is pre-created by a fixture: each account is
    born from its own first request, which is exactly how a new teammate
    arrives in production.
    """
    app, _, _ = env
    emily = token_for(signing_key, "emily@example.com")
    colleague = token_for(signing_key, "colleague@example.com")

    with client(app) as c:
        # Emily arrives first and creates a folder with an item.
        emily_me = c.get("/api/v5/me", headers=hdr(emily)).json()
        created = c.post("/api/v5/folders", json={"name": "Q1 asks"},
                         headers=hdr(emily))
        assert created.status_code == 201
        folder_id = created.json()["id"]
        added = c.post(f"/api/v5/folders/{folder_id}/items",
                       json={"ein": "131635294"}, headers=hdr(emily))
        assert added.status_code == 201

        # The colleague logs in for the first time, seconds later.
        colleague_me = c.get("/api/v5/me", headers=hdr(colleague)).json()
        seen = c.get("/api/v5/folders", headers=hdr(colleague))

    assert emily_me["email"] != colleague_me["email"], "must be two users"
    assert emily_me["team_id"] == colleague_me["team_id"], (
        "two first-time logins landed in different teams -- a new teammate "
        "would see an empty list")

    folders = seen.json()
    assert len(folders) == 1, "the colleague sees no folder, or sees extras"
    assert folders[0]["id"] == folder_id
    assert folders[0]["name"] == "Q1 asks"
    assert [i["ein"] for i in folders[0]["items"]] == ["131635294"], (
        "the folder is visible but its items are not")


def test_missing_team_row_fails_loudly_and_creates_nothing(env, no_team,
                                                           signing_key):
    """An unmigrated database refuses service instead of partitioning users.

    The application used to create a team when the table was empty. Under
    concurrency that produced one team per racing login and split the team's
    saved folders across them silently -- a colleague would simply see an
    empty list, with nothing anywhere reporting a fault. A 503 is a far better
    outcome than a database that looks fine and is quietly wrong.
    """
    app, db_session, _ = env
    from models_db import Team, User

    with client(app) as c:
        response = c.get("/api/v5/me",
                         headers=hdr(token_for(signing_key, "first@example.com")))
    assert response.status_code == 503
    assert "not initialised" in response.json()["detail"]

    session = db_session._SessionLocal()
    teams = session.query(Team).count()
    users = session.query(User).count()
    session.close()
    assert teams == 0, "a team was created despite the refusal"
    assert users == 0, "a user was created without a team"


def test_concurrent_first_logins_never_partition(env, no_team, signing_key):
    """The regression test for the measured failure: 8 racing first-logins.

    Against an empty table this previously created six teams and scattered
    eight users across them. Now every one of them must fail, and the database
    must be untouched.
    """
    import threading

    app, db_session, _ = env
    from models_db import Team, User

    codes: dict[int, int] = {}

    def login(i: int) -> None:
        with client(app) as c:
            codes[i] = c.get(
                "/api/v5/me",
                headers=hdr(token_for(signing_key, f"racer{i}@example.com")),
            ).status_code

    threads = [threading.Thread(target=login, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    session = db_session._SessionLocal()
    teams = session.query(Team).count()
    users = session.query(User).count()
    session.close()

    assert set(codes.values()) == {503}, f"expected all 503, got {codes}"
    assert teams == 0, f"{teams} teams created by racing logins"
    assert users == 0, f"{users} users created without a team"


def test_only_one_team_is_ever_created(env, clean, signing_key):
    """Every new account joins the existing team rather than founding one."""
    app, db_session, _ = env
    from models_db import Team, User

    with client(app) as c:
        for n in range(5):
            r = c.get("/api/v5/me",
                      headers=hdr(token_for(signing_key, f"u{n}@example.com")))
            assert r.status_code == 200

    session = db_session._SessionLocal()
    teams = session.query(Team).count()
    users = session.query(User).count()
    team_ids = {u.team_id for u in session.query(User).all()}
    session.close()
    assert users == 5
    assert teams == 1, f"{teams} teams exist; accounts would be partitioned"
    assert len(team_ids) == 1


def test_the_colleague_can_edit_what_emily_created(env, clean, signing_key):
    """Shared means writable, not just readable."""
    app, _, _ = env
    emily = token_for(signing_key, "emily@example.com")
    colleague = token_for(signing_key, "colleague@example.com")

    with client(app) as c:
        folder_id = c.post("/api/v5/folders", json={"name": "Shared"},
                           headers=hdr(emily)).json()["id"]
        add = c.post(f"/api/v5/folders/{folder_id}/items",
                     json={"ein": "131635294"}, headers=hdr(colleague))
        rename = c.patch(f"/api/v5/folders/{folder_id}",
                         json={"name": "Renamed by colleague"},
                         headers=hdr(colleague))
        final = c.get("/api/v5/folders", headers=hdr(emily)).json()

    assert add.status_code == 201
    assert rename.status_code == 200
    assert final[0]["name"] == "Renamed by colleague"
    assert [i["ein"] for i in final[0]["items"]] == ["131635294"]


# --- 4. attribution ----------------------------------------------------------

def test_attribution_distinguishes_the_two_users(env, clean, signing_key):
    """Shared folders make "who did this" the only way to read the history."""
    app, _, _ = env
    emily = token_for(signing_key, "emily@example.com")
    colleague = token_for(signing_key, "colleague@example.com")

    with client(app) as c:
        folder_id = c.post("/api/v5/folders", json={"name": "Attribution"},
                           headers=hdr(emily)).json()["id"]
        c.post(f"/api/v5/folders/{folder_id}/items",
               json={"ein": "111111111"}, headers=hdr(emily))
        c.post(f"/api/v5/folders/{folder_id}/items",
               json={"ein": "222222222"}, headers=hdr(colleague))
        folder = c.get("/api/v5/folders", headers=hdr(emily)).json()[0]

    assert folder["created_by"] == "emily@example.com"
    by_ein = {i["ein"]: i["added_by"] for i in folder["items"]}
    assert by_ein == {
        "111111111": "emily@example.com",
        "222222222": "colleague@example.com",
    }


def test_rename_does_not_rewrite_created_by(env, clean, signing_key):
    """Editing someone's folder must not claim authorship of it."""
    app, _, _ = env
    emily = token_for(signing_key, "emily@example.com")
    colleague = token_for(signing_key, "colleague@example.com")

    with client(app) as c:
        folder_id = c.post("/api/v5/folders", json={"name": "Original"},
                           headers=hdr(emily)).json()["id"]
        c.patch(f"/api/v5/folders/{folder_id}", json={"name": "Edited"},
                headers=hdr(colleague))
        folder = c.get("/api/v5/folders", headers=hdr(emily)).json()[0]

    assert folder["created_by"] == "emily@example.com"


# --- 5. header name and case -------------------------------------------------

@pytest.mark.parametrize("header_name", [
    "Cf-Access-Jwt-Assertion",   # what Cloudflare documents and sends
    "cf-access-jwt-assertion",   # HTTP/2 lowercases every header name
    "CF-ACCESS-JWT-ASSERTION",
    "cF-aCcEsS-jWt-AsSeRtIoN",
])
def test_header_lookup_is_case_insensitive(env, clean, signing_key,
                                           header_name):
    """nginx and HTTP/2 both normalise case; the code must not care."""
    app, _, _ = env
    token = token_for(signing_key, "case@example.com")
    with client(app) as c:
        response = c.get("/api/v5/me", headers=hdr(token, header_name))
    assert response.status_code == 200, f"{header_name} was not recognised"


def test_underscore_variant_is_not_accepted(env, clean, signing_key):
    """Documents the boundary: only the hyphenated name is the header.

    nginx drops underscored headers by default anyway, so a client sending
    this form would be rejected before reaching the app.
    """
    app, _, _ = env
    token = token_for(signing_key, "case@example.com")
    with client(app) as c:
        response = c.get("/api/v5/me",
                         headers=hdr(token, "Cf_Access_Jwt_Assertion"))
    assert response.status_code == 401


# --- last_seen_at ------------------------------------------------------------

def test_last_seen_at_advances_on_a_later_request(env, clean, signing_key):
    app, db_session, _ = env
    from models_db import User

    token = token_for(signing_key, "seen@example.com")
    with client(app) as c:
        c.get("/api/v5/me", headers=hdr(token))
        session = db_session._SessionLocal()
        first = session.query(User).filter_by(email="seen@example.com").one()
        first_seen = first.last_seen_at
        created = first.created_at
        session.close()

        time.sleep(0.05)
        c.get("/api/v5/me", headers=hdr(token))

    session = db_session._SessionLocal()
    again = session.query(User).filter_by(email="seen@example.com").one()
    assert again.last_seen_at > first_seen
    assert again.created_at == created, "created_at must not drift"
    session.close()
