# Foundation Explorer

Local, read-only web UI over the grant-research pipeline: 139,965 US
private foundations, 5M+ grants, faith alignment scores, application
contacts. Two processes: FastAPI backend + Vite/React frontend.

## Run it

```bash
# Terminal 1 — backend (localhost:8000)
cd foundation-explorer/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend (localhost:5173)
cd foundation-explorer/frontend
npm install
npm run dev
```

Open http://localhost:5173. API docs at http://localhost:8000/docs.

## How data flows

- On first startup the backend builds `data/explorer.db` from
  `foundation_database.csv` (the national export) and indexes it. It
  rebuilds automatically whenever the CSV is newer than the db.
- `data/grants.db` (the pipeline database) is ATTACHed **read-only** for
  grants, charitable activities, and recipient drill-downs. The backend
  never writes to it (it only adds two safe indexes on first run).
- Regenerate `foundation_database.csv` with `python3 -m src.export` from
  the repo root after any pipeline run; the explorer picks it up on
  restart.

## Pages

| Route | What it shows |
|---|---|
| `/` | KPIs, score + size distributions, top 10, application donut |
| `/foundations` | Main table: filters, search, sort, CSV export, detail slide-over (Overview / Grants / Recipients / Activities / Raw) |
| `/grants` | 5M-grant explorer with amount/year/state/foreign filters |
| `/recipients` | Knowledge-base explorer with tag/source filters + funder drill-down |
| `/analytics` | State breakdowns, yearly trends, top-100 leaderboard |
| `/data-quality` | Field coverage bars, pipeline reconciliation, classification status |

## Env overrides (backend)

- `GRANTS_DB` — path to grants.db (default `../../data/grants.db`)
- `EXPLORER_DB` — path for the derived db
- `UNIVERSE_CSV` — path to foundation_database.csv
