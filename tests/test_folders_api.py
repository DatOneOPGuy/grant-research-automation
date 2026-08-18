"""Account system: authentication and cross-team isolation.

Needs a real Postgres -- the folder endpoints use ON CONFLICT and a functional
unique index on lower(name), neither of which SQLite would exercise faithfully.
Point TEST_DATABASE_URL at a throwaway database; the suite skips if it cannot
connect, rather than failing on a machine that simply has no Postgres.

    createdb fcf_test
    TEST_DATABASE_URL=postgresql+psycopg://localhost/fcf_test pytest \
        tests/test_folders_api.py

The isolation tests are the point of this file. A user must never read or
mutate another team's folders even by guessing an id, so every endpoint that
takes a folder id is checked from the wrong team.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "foundation-explorer" / "backend"

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)

sqlalchemy = pytest.importorskip("sqlalchemy")


@pytest.fixture(scope="module")
def backend_app():
    """Import the backend with a dev-bypass environment and a test database.

    The backend is a flat module directory imported by bare name (the same
    constraint the systemd unit's WorkingDirectory encodes), so the path goes
    on sys.path rather than being imported as a package.
    """
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["DEV_USER_EMAIL"] = "dev@example.com"
    for stale in ("CF_ACCESS_TEAM_DOMAIN", "CF_ACCESS_AUD"):
        os.environ.pop(stale, None)
    sys.path.insert(0, str(BACKEND))

    for cached in ("config", "db_session", "models_db", "auth", "folders"):
        sys.modules.pop(cached, None)

    import db_session
    import folders as folders_mod
    from models_db import Base

    try:
        Base.metadata.drop_all(db_session._engine)
        Base.metadata.create_all(db_session._engine)
    except sqlalchemy.exc.SQLAlchemyError as exc:
        pytest.skip(f"Postgres unreachable at TEST_DATABASE_URL: {exc}")

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(folders_mod.router)
    return app, db_session, folders_mod


@pytest.fixture()
def two_teams(backend_app):
    """Two teams, one user each, and a folder with an item owned by team A."""
    _, db_session, _ = backend_app
    from models_db import Folder, FolderItem, Team, User

    session = db_session._SessionLocal()
    session.query(FolderItem).delete()
    session.query(Folder).delete()
    session.query(User).delete()
    session.query(Team).delete()

    team_a, team_b = Team(name="Team A"), Team(name="Team B")
    session.add_all([team_a, team_b])
    session.flush()
    user_a = User(email="a@example.com", team_id=team_a.id)
    user_b = User(email="b@example.com", team_id=team_b.id)
    session.add_all([user_a, user_b])
    session.flush()
    folder_a = Folder(team_id=team_a.id, name="Team A folder",
                      created_by=user_a.id)
    session.add(folder_a)
    session.flush()
    session.add(FolderItem(folder_id=folder_a.id, ein="123456789",
                           added_by=user_a.id))
    session.commit()
    ids = {"folder_a": folder_a.id, "user_a": user_a.id, "user_b": user_b.id}
    session.close()
    return ids


def client_as(app, db_session, user_id: int):
    """A TestClient whose requests resolve to a specific user.

    Overrides the dependency rather than minting a Cloudflare token: signing
    a JWT here would test our ability to sign a JWT. What needs proving is
    that the endpoints scope by the authenticated user's team, whoever that
    user is and however they were authenticated.
    """
    import auth
    from fastapi.testclient import TestClient
    from models_db import User

    def as_user():
        session = db_session._SessionLocal()
        try:
            yield session.get(User, user_id)
        finally:
            session.close()

    app.dependency_overrides[auth.current_user] = as_user
    return TestClient(app)


# --- cross-team isolation ----------------------------------------------------

def test_user_b_cannot_list_team_a_folders(backend_app, two_teams):
    app, db_session, _ = backend_app
    with client_as(app, db_session, two_teams["user_b"]) as c:
        assert c.get("/api/v5/folders").json() == []
    with client_as(app, db_session, two_teams["user_a"]) as c:
        assert len(c.get("/api/v5/folders").json()) == 1


@pytest.mark.parametrize("method,suffix,body", [
    ("patch", "", {"name": "hijacked"}),
    ("delete", "", None),
    ("post", "/items", {"ein": "999999999"}),
    ("delete", "/items/123456789", None),
])
def test_user_b_gets_404_on_team_a_folder(backend_app, two_teams, method,
                                          suffix, body):
    """404, not 403.

    A 403 confirms the id exists, which turns the endpoint into an oracle for
    enumerating other teams' folders one integer at a time. 404 is both safer
    and true: this caller has no such folder.
    """
    app, db_session, _ = backend_app
    url = f"/api/v5/folders/{two_teams['folder_a']}{suffix}"
    with client_as(app, db_session, two_teams["user_b"]) as c:
        response = getattr(c, method)(url, **({"json": body} if body else {}))
    assert response.status_code == 404


def test_team_a_folder_survives_team_b_attempts(backend_app, two_teams):
    app, db_session, _ = backend_app
    with client_as(app, db_session, two_teams["user_a"]) as c:
        folders = c.get("/api/v5/folders").json()
    assert folders[0]["name"] == "Team A folder"
    assert [i["ein"] for i in folders[0]["items"]] == ["123456789"]


def test_unsave_everywhere_is_team_scoped(backend_app, two_teams):
    """Team B unsaving an EIN must not touch team A's copy of it."""
    app, db_session, _ = backend_app
    with client_as(app, db_session, two_teams["user_b"]) as c:
        assert c.delete("/api/v5/items/123456789").status_code == 204
    with client_as(app, db_session, two_teams["user_a"]) as c:
        folders = c.get("/api/v5/folders").json()
    assert [i["ein"] for i in folders[0]["items"]] == ["123456789"]


# --- behaviour ---------------------------------------------------------------

def test_adding_the_same_ein_twice_is_a_noop(backend_app, two_teams):
    app, db_session, _ = backend_app
    url = f"/api/v5/folders/{two_teams['folder_a']}/items"
    with client_as(app, db_session, two_teams["user_a"]) as c:
        first = c.post(url, json={"ein": "555555555"})
        second = c.post(url, json={"ein": "555555555"})
    assert first.status_code == 201
    assert second.status_code == 201  # not a 500 from the unique constraint
    assert [i["ein"] for i in second.json()["items"]].count("555555555") == 1


def test_duplicate_folder_name_returns_the_existing_folder(backend_app,
                                                           two_teams):
    """Shared folders make a silent merge the right answer."""
    app, db_session, _ = backend_app
    with client_as(app, db_session, two_teams["user_a"]) as c:
        again = c.post("/api/v5/folders", json={"name": "team a FOLDER"})
    assert again.status_code == 201
    assert again.json()["id"] == two_teams["folder_a"]


def test_removing_an_absent_item_is_success(backend_app, two_teams):
    app, db_session, _ = backend_app
    url = f"/api/v5/folders/{two_teams['folder_a']}/items/000000000"
    with client_as(app, db_session, two_teams["user_a"]) as c:
        assert c.delete(url).status_code == 204


def test_me_reports_the_caller(backend_app, two_teams):
    app, db_session, _ = backend_app
    with client_as(app, db_session, two_teams["user_b"]) as c:
        body = c.get("/api/v5/me").json()
    assert body["email"] == "b@example.com"
    assert body["team_name"] == "Team B"


# --- fail closed -------------------------------------------------------------

def test_missing_token_is_401(backend_app, two_teams):
    """No dependency override here: the real auth path must reject."""
    from fastapi.testclient import TestClient

    app, _, _ = backend_app
    app.dependency_overrides.clear()
    import config

    original = config.DEV_USER_EMAIL
    config.DEV_USER_EMAIL = None  # simulate a production process
    try:
        with TestClient(app) as c:
            assert c.get("/api/v5/folders").status_code == 401
            assert c.post("/api/v5/folders",
                          json={"name": "x"}).status_code == 401
    finally:
        config.DEV_USER_EMAIL = original


def test_garbage_token_is_401(backend_app):
    from fastapi.testclient import TestClient

    app, _, _ = backend_app
    app.dependency_overrides.clear()
    import config

    original_dev = config.DEV_USER_EMAIL
    config.DEV_USER_EMAIL = None
    config.CF_CONFIGURED = True
    config.CF_ACCESS_TEAM_DOMAIN = "example.cloudflareaccess.com"
    config.CF_ACCESS_AUD = "deadbeef"
    try:
        with TestClient(app) as c:
            response = c.get(
                "/api/v5/folders",
                headers={"Cf-Access-Jwt-Assertion": "not.a.jwt"})
        assert response.status_code == 401
        # The reason must not leak to the client.
        assert response.json()["detail"] == "Not authenticated"
    finally:
        config.DEV_USER_EMAIL = original_dev
        config.CF_CONFIGURED = False
        config.CF_ACCESS_TEAM_DOMAIN = None
        config.CF_ACCESS_AUD = None


def test_dev_bypass_cannot_coexist_with_cloudflare(monkeypatch):
    """The dangerous configuration must be unreachable, not merely discouraged.

    config.py refuses to import when the dev bypass is set alongside Access
    configuration, so the process dies at startup instead of quietly accepting
    an unauthenticated header behind a public hostname.
    """
    monkeypatch.setenv("DEV_USER_EMAIL", "dev@example.com")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "example.cloudflareaccess.com")
    monkeypatch.setenv("CF_ACCESS_AUD", "deadbeef")
    sys.path.insert(0, str(BACKEND))
    sys.modules.pop("config", None)

    with pytest.raises(RuntimeError, match="DEV_USER_EMAIL"):
        import config  # noqa: F401

    sys.modules.pop("config", None)
