"""Foundation Explorer v5 API — serves only the honest v5 read model.

Deliberately does NOT mount the legacy v1 routes: v1 data carries known-false
claims (future commitments as paid, name-merged identities, inflated
verdicts). Run: uvicorn main_v5:app --port 8000
"""

import logging
from pathlib import Path

import v5
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Foundation Explorer v5", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if not Path(v5.DB_PATH).exists():
        raise RuntimeError(
            f"Read model missing: {v5.DB_PATH}. "
            "Run: python3 -m src.build_explorer_v5")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": str(v5.DB_PATH)}


app.include_router(v5.router)
