"""Foundation Explorer API — read-only over the grant-research pipeline."""

import logging

from db import build_explorer_db, ensure_grants_indexes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import analytics, export, foundations, grants, recipients

logging.basicConfig(level=logging.INFO)

app = FastAPI(title='Foundation Explorer API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_methods=['GET'],
    allow_headers=['*'],
)


@app.on_event('startup')
def startup():
    build_explorer_db()
    ensure_grants_indexes()


@app.get('/api/health')
def health():
    return {'status': 'ok'}


for r in (foundations, grants, recipients, analytics, export):
    app.include_router(r.router)
