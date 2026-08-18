# Deploying Foundation Explorer

Production: <https://fcf.drakesdev.com> — DigitalOcean droplet `162.243.29.41`
(Ubuntu 24.04, 4 GB / 80 GB, NYC2), ssh alias `fcf`.

This replaces the old Netlify static deployment. The live site serves the
**full** database through the FastAPI backend; the static demo build still
exists but is a separate artifact (see [Demo build](#demo-build)).

## Layout on the box

| Path | What |
|---|---|
| `/opt/fcf/` | The repo, **rsynced** from the laptop — not a clone, there is no deploy key |
| `/opt/fcf/data/explorer_v5.db` | ~1.33 GB read model, rsynced. Read-only, rebuildable |
| `/opt/fcf/venv/` | Python deps, installed from `backend/requirements.lock` |
| `/var/www/fcf/` | Built SPA (~500 KB) |
| Postgres (local, `:5432`) | Accounts and shared saved folders. **Not** rebuildable — back this up |
| `/etc/systemd/system/fcf.service` | The uvicorn unit, plus the `Environment=` lines |
| `/etc/nginx/sites-available/fcf` | TLS termination, `/api/` proxy, SPA fallback |

Two datastores, with opposite properties. `explorer_v5.db` is a compiled
artifact: if it is lost, rebuild it from the pipeline. Postgres holds folders
and notes that people typed, which exist nowhere else. Anything destructive
should treat them differently for exactly that reason.

`sites-enabled/default` has been removed. nginx proxies `/api/` to
`127.0.0.1:8000` and serves `/var/www/fcf` with
`try_files $uri $uri/ /index.html` for client-side routing. TLS is certbot
(expires 2026-11-16, auto-renew configured).

Frontend and API are same-origin, so the `allow_origins=["http://localhost:5173"]`
CORS middleware in `foundation-explorer/backend/main_v5.py:18` never fires in
production. It is dead config there, still needed for local `vite dev`.

## WorkingDirectory is mandatory

```ini
WorkingDirectory=/opt/fcf/foundation-explorer/backend
ExecStart=/opt/fcf/venv/bin/uvicorn main_v5:app --host 127.0.0.1 --port 8000
Environment=DATABASE_URL=postgresql+psycopg://fcf:PASSWORD@127.0.0.1:5432/fcf
Environment=CF_ACCESS_TEAM_DOMAIN=yourteam.cloudflareaccess.com
Environment=CF_ACCESS_AUD=<application audience tag>
```

The three `Environment=` lines are new with the account system — see
[Accounts](#accounts-postgres-and-cloudflare-access). Use
`systemctl edit fcf` and an override file rather than putting the password in
a unit that gets rsynced, or point `EnvironmentFile=` at a root-owned
`/etc/fcf.env` with mode 600.

`main_v5.py` does a bare `import v5` (not `from .v5 import ...` — the backend
is a flat directory of modules, not a package). That resolves only when the
process's working directory *is* the backend directory. Change or drop
`WorkingDirectory` and the unit dies at import with `ModuleNotFoundError: v5`.
Same reason `main_v5:app` works as a bare module path rather than a dotted one.

## Deploying the frontend

```bash
cd foundation-explorer/frontend
npm run build
rsync -av --delete \
  --exclude 'demo/' --exclude 'demo-v5/' --exclude 'sample/' --exclude 'report/' \
  dist/ fcf:/var/www/fcf/
```

### The excludes are load-bearing

Vite copies everything in `public/` into `dist/` wholesale. `public/` currently
holds ~967 MB of pre-generated static shards:

| Directory | Size |
|---|---|
| `public/demo-v5/` | 930 MB |
| `public/demo/` | 37 MB |
| `public/sample/` | 292 KB |
| `public/report/` | 44 KB |

Those shards are **dumps of the compiled database**. Serving them from
`/var/www/fcf` would publish the licensed dataset as flat, unauthenticated JSON
at predictable URLs — defeating any auth gate placed in front of the app, and
breaching LICENSE-LIFETIME.md §2 ("the compiled database and derived analysis
may not be resold, republished, sub-licensed or shared outside the licensed
organisation").

`--delete` plus a forgotten exclude is also how you'd blow the 80 GB disk.

**Proper fix, not yet done:** move these directories out of `public/` entirely
(e.g. to `foundation-explorer/demo-data/`, wired in only for the demo build) so
correctness does not depend on remembering four flags. Until then, treat the
exclude list as part of the command, never shortened.

## Deploying the backend

```bash
rsync -av --delete \
  --exclude '.git/' --exclude 'node_modules/' --exclude 'data/' \
  ./ fcf:/opt/fcf/
ssh fcf 'systemctl restart fcf'
```

Exclude `data/` so a repo sync never touches the 1.33 GB database — that has
its own procedure below. Check `journalctl -u fcf -n 50` after a restart; a
bad import fails at startup, and `main_v5.py` also raises deliberately if
`explorer_v5.db` is missing.

If the sync changed anything under `backend/`, reinstall from the lockfile and
run any new migrations before restarting:

```bash
ssh fcf '/opt/fcf/venv/bin/pip install -r \
           /opt/fcf/foundation-explorer/backend/requirements.lock'
ssh fcf 'cd /opt/fcf/foundation-explorer/backend && \
         /opt/fcf/venv/bin/alembic upgrade head'
ssh fcf 'systemctl restart fcf'
```

## Accounts: Postgres and Cloudflare Access

Saved folders are shared across the team and live in Postgres. Identity comes
from Cloudflare Access — no passwords, sessions, or reset flow are stored by
this application.

### One-time Postgres setup

```bash
ssh fcf
apt install -y postgresql
sudo -u postgres createuser --pwprompt fcf
sudo -u postgres createdb --owner=fcf fcf
```

Keep it bound to localhost (the Debian/Ubuntu default). Nothing outside the
droplet needs to reach it, and the API connects over `127.0.0.1`.

### Environment

Three variables, read at startup, no defaults. Template in `.env.example`.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://fcf:PASSWORD@127.0.0.1:5432/fcf` |
| `CF_ACCESS_TEAM_DOMAIN` | Zero Trust team domain, no scheme. Determines the JWKS endpoint and the expected issuer |
| `CF_ACCESS_AUD` | Application Audience tag from the Access application. Without it, any token the team domain issues for any app would be accepted |

There is also `DEV_USER_EMAIL`, for local work without Cloudflare in front.
**The process refuses to start if it is set alongside either `CF_ACCESS_*`
variable.** The bypass authenticates every request as that email without
checking a token, so the unsafe combination is made unbootable rather than
merely discouraged — a crash on deploy is a better failure than a public
hostname quietly trusting an unauthenticated header.

### Migrations

Alembic, run from the backend directory — the same `WorkingDirectory` the
systemd unit requires, so there is only one path convention to remember.
`alembic.ini` has a deliberately blank `sqlalchemy.url`; `env.py` reads
`DATABASE_URL` instead, so no DSN is ever committed.

```bash
cd /opt/fcf/foundation-explorer/backend
/opt/fcf/venv/bin/alembic upgrade head     # apply
/opt/fcf/venv/bin/alembic current          # what is applied
/opt/fcf/venv/bin/alembic check            # does the schema match the models
```

**Migrations are an explicit deploy step and are never run at app startup.**
A process that migrates on boot turns a restart into a schema change, and
turns a crashloop into a schema change repeated several times a second.

The initial revision seeds one team. Every user is assigned to it on first
login; `team_id` exists on every table so a second team is a data change
rather than a migration.

### Backups

Unlike `explorer_v5.db`, this cannot be regenerated:

```bash
ssh fcf 'sudo -u postgres pg_dump fcf | gzip' > fcf-$(date +%F).sql.gz
```

Small enough to take before any deploy that includes a migration.

### Health

`/api/health` reports components rather than a bare OK:

```json
{"status": "ok", "model": "/opt/fcf/data/explorer_v5.db",
 "accounts": {"status": "ok", "auth_mode": "cloudflare"}}
```

`status` is `degraded` when Postgres is unreachable. That case is deliberately
**not** fatal: the 13 read routes keep serving, and only the folder endpoints
return 503. Taking the whole site down to protect the saved-folder feature
would be the wrong trade. A monitor that only checks the HTTP status code will
miss this, so alert on `accounts.status` too.

`auth_mode` is `cloudflare`, `dev-bypass`, or `unconfigured`. In production it
must read `cloudflare`.

### Tests

Cross-team isolation is the thing worth verifying: a user must never read or
mutate another team's folders even by guessing an id. Those tests need a real
Postgres and skip without one.

```bash
createdb fcf_test
TEST_DATABASE_URL=postgresql+psycopg://localhost/fcf_test \
  pytest tests/test_folders_api.py
```

## Refreshing the database

Never rebuild in place. `src/build_explorer_v5` drops and recreates the file,
and the API process holds it open — an in-place rebuild yields a live server
reading a deleted inode, then hard errors.

```bash
# 1. Build locally
python3 -m src.build_explorer_v5

# 2. Ship to a temp name (same filesystem as the target)
rsync -av --progress data/explorer_v5.db fcf:/opt/fcf/data/explorer_v5.db.new

# 3. Atomic swap, then restart
ssh fcf 'mv /opt/fcf/data/explorer_v5.db.new /opt/fcf/data/explorer_v5.db \
         && systemctl restart fcf'

# 4. Verify
curl -s https://fcf.drakesdev.com/api/health
```

The `mv` must be a rename within one filesystem, which is why the temp file
goes in `/opt/fcf/data/` rather than `/tmp`. Keep an eye on free space: two
copies of the db is ~2.7 GB of the 80 GB disk.

Note the SQLite hazards documented for `grants_v2.db` apply here too — never
move a `.db` without its `-wal`/`-shm` sidecars if the source was checkpointed
mid-write. Build, let the writer exit cleanly, then ship.

## Demo build

```bash
npm run build:demo   # DEMO=1 vite build
```

`vite.config.ts` injects `import.meta.env.VITE_DEMO` via `define` from either
`DEMO=1` or `VITE_DEMO=1`, and `apiV5.ts:693` reads that flag to switch on the
client-side static adapter. **The `define` block and the npm script are
coupled** — the shell variable is `DEMO`, which Vite would not expose on its
own without the explicit `define`.

Previously `STATIC_MODE` was inferred from the hostname (anything not
`localhost`/`127.0.0.1` was treated as static), which is why the first
production deploy served demo data and never called the API.

A demo build *does* need the `public/` shards, so it uses `dist/` unfiltered —
and must not be rsynced to `/var/www/fcf`. It also keeps the old
localStorage-backed saved folders, because a static build has no API to talk
to; `SavedProvider` picks the store from `STATIC_MODE`.

## Security state

- **Writes are authenticated; reads are not.** Every folder endpoint requires
  a verified Access token and is scoped to the caller's team. The 13 read
  routes are unchanged and unauthenticated at the application layer, so the
  full database is readable by anything that reaches the origin.
- **Cloudflare Access is therefore the only gate on the data**, and it
  protects the *hostname*. Until `ufw` restricts `:443` to Cloudflare's
  published IP ranges, `https://162.243.29.41` is a direct bypass around the
  policy — and now that accounts exist, it is also a way to reach the API
  without ever presenting a token. This is the highest-value item outstanding.
- SSH key rotation: new key installed, old key removed from `authorized_keys`
  and confirmed rejected. Outstanding: delete the old key from the DigitalOcean
  dashboard and check whether it is registered as a GitHub deploy key. (The
  keypair is not in this repo — not tracked, not in history, not on disk — so
  there is nothing here to purge with git-filter-repo. If it exists, it is
  somewhere else.)

## Known gaps

- **Error copy names localhost.** Three strings tell production users to start
  a backend on `localhost:8000`: `pages/Dashboard.tsx:27`,
  `pages/Foundations.tsx:183`, `components/foundations/DetailPanel.tsx:164`.
- **Demo shards still live in `public/`.** The four `--exclude` flags are the
  only thing keeping them off the server. Move them out.
- **Netlify remnants.** `foundation-explorer/frontend/netlify.toml` and
  `.netlify/` are still present; the SPA redirect they define is now nginx's
  `try_files`. Remove once the Netlify site is decommissioned.
- **Pending kernel reboot** on the droplet.
- **No Postgres backup schedule.** The `pg_dump` above is manual.

Closed since the last revision: dependency pinning. `backend/requirements.txt`
now pins every direct dependency and `backend/requirements.lock` pins the full
resolved set, including `starlette==1.6.0` — the version that was drifting.
Install on the droplet from the lock, not from `requirements.txt`.
