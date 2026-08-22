"""Foundation Explorer v5 API — serves only the honest v5 read model.

Deliberately does NOT mount the legacy v1 routes: v1 data carries known-false
claims (future commitments as paid, name-merged identities, inflated
verdicts). Run: uvicorn main_v5:app --port 8000

Two routers: v5.router is the read model (13 GETs over explorer_v5.db, no
auth at the application layer -- Cloudflare Access gates the hostname), and
folders.router is the account system (Postgres, every route authenticated).
"""

import logging
from pathlib import Path

import db_session
import folders
import search
import v5
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Foundation Explorer v5", version="5.0.0")

# Only reachable in local development: in production nginx serves the SPA and
# proxies /api/ on the same origin, so no preflight ever happens.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    # The read model is the product. Without it there is nothing to serve, so
    # refusing to start is right here.
    if not Path(v5.DB_PATH).exists():
        raise RuntimeError(
            f"Read model missing: {v5.DB_PATH}. "
            "Run: python3 -m src.build_explorer_v5")

    # Postgres is not. If it is unreachable the Explorer still answers every
    # read route, and taking the site down to protect the saved-folder feature
    # would be the wrong trade -- so this reports and continues.
    if db_session.configured():
        state = db_session.health()
        if state["status"] == "ok":
            log.info("Accounts: Postgres reachable, auth mode %s",
                     config.auth_mode())
        else:
            log.error(
                "Accounts DEGRADED: Postgres %s (%s). Read routes are "
                "unaffected; saved folders will return 503.",
                state["status"], state.get("detail"))
    else:
        log.warning("Accounts disabled: DATABASE_URL is not set.")

    if config.auth_mode() == "dev-bypass":
        log.warning(
            "DEV BYPASS ACTIVE: every request is authenticated as %s. This "
            "cannot happen with Cloudflare Access configured -- config.py "
            "refuses to start in that combination.", config.DEV_USER_EMAIL)


@app.get("/api/health")
def health() -> dict:
    """Liveness plus a component breakdown.

    Degraded rather than dead: 200 with accounts.status != "ok" is the honest
    signal when reads work and writes do not. A monitor that only checks the
    status code would otherwise see a healthy site with a broken feature.
    """
    accounts = db_session.health()
    return {
        "status": "ok" if accounts["status"] in ("ok", "disabled")
                  else "degraded",
        "model": str(v5.DB_PATH),
        "accounts": {**accounts, "auth_mode": config.auth_mode()},
    }


app.include_router(v5.router)
app.include_router(search.router)
app.include_router(folders.router)
