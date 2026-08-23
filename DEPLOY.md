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

## Releasing an update

### Downtime, measured

| Step | Interruption | What a user sees |
|---|---|---|
| Frontend deploy (two-phase, below) | **none** | nothing |
| `systemctl restart fcf` | **~1.5 s** | one failed API call, then recovery |
| `alembic upgrade head` | none by itself | nothing |
| Database refresh (`mv` + restart) | ~1.5 s | as above |
| Pruning old asset bundles | none, if done later | nothing |

The 1.5 s is `0.25 s` to stop, `~1.1 s` of Python interpreter and imports, and
`~0.07 s` of application startup, taken from `journalctl -o short-precise` and
by timing `import main_v5` on the box. During that window nginx cannot reach
`127.0.0.1:8000` and returns **502**.

The frontend's react-query is configured with `retry: 1`, so a single call
crossing the restart usually retries and succeeds. A save in flight will show
the "That change was not saved" banner and can simply be repeated — nothing is
written half-way, because every mutation is one transaction.

**There is no way to reach zero backend downtime with the current single-process
setup.** See [Toward zero downtime](#toward-zero-downtime) for the upgrade
path. Until then, deploy when the team is not mid-session; 1.5 s is cheap but
it is not nothing.

### Order of operations

Deploy back to front. The API tolerates an older frontend far better than a new
frontend tolerates an older API — a new bundle calling an endpoint that does not
exist yet fails with no recovery, whereas an old bundle simply does not call the
new endpoint.

```
1. pre-flight   → tests, lint, build, confirm clean tree
2. backup       → pg_dump, if the release contains a migration
3. backend      → rsync, pip install, alembic upgrade, restart
4. verify       → health, a read route, a 401 on folders
5. frontend     → phase 1 (additive rsync)
6. verify       → load the site, check the bundle hash
7. later        → prune superseded asset bundles
```

Skip steps that do not apply: a copy-only frontend change needs 1, 5, 6, 7.

### Pre-flight, on the laptop

```bash
cd foundation-explorer/frontend && npm run lint && npx tsc -b --force && npm run test:saved
cd ../.. && python3 -m ruff check foundation-explorer/backend/ tests/
python3 -m pytest tests/ -q                       # pipeline suite

# Account + identity suite needs a Postgres:
createdb fcf_test
TEST_DATABASE_URL=postgresql+psycopg://localhost/fcf_test \
  foundation-explorer/backend/.venv/bin/python -m pytest \
  tests/test_folders_api.py tests/test_access_identity.py tests/test_jwks_client.py

git status --porcelain     # must be empty; deploy what is committed
git push
```

A dirty tree is the most common way to ship something that is not in git and
cannot be rolled back to. `/opt/fcf` is an rsync target, not a clone, so the
droplet has no record of what version it is running — the repo is the only
record, which is why the tree must be clean.

### Backend release

```bash
# 2. Back up first if this release migrates. Cheap; do it anyway.
ssh fcf 'sudo -u postgres pg_dump fcf | gzip' > fcf-$(date +%F-%H%M).sql.gz

# 3. Ship code. Note the excludes -- venv/ lives inside the target and
#    --delete would remove the interpreter mid-deploy.
rsync -av --delete \
  --exclude 'venv/' --exclude '.venv/' --exclude 'data/' --exclude '.git/' \
  --exclude 'node_modules/' --exclude 'foundation-explorer/frontend/' \
  --exclude '__pycache__/' --exclude '*.pyc' \
  ./ fcf:/opt/fcf/

# Dependencies, only if requirements.lock changed
ssh fcf '/opt/fcf/venv/bin/pip install -r \
           /opt/fcf/foundation-explorer/backend/requirements.lock'

# Migrations, only if a new revision was added. Explicit, never at startup.
ssh fcf 'cd /opt/fcf/foundation-explorer/backend && \
         DATABASE_URL=$(grep ^DATABASE_URL= /etc/fcf/fcf.env | cut -d= -f2-) \
         /opt/fcf/venv/bin/alembic upgrade head'

ssh fcf 'systemctl restart fcf'
```

`alembic` imports `config`, which validates the whole Access environment. Pass
`DATABASE_URL` alone as above rather than sourcing the env file — with
`CF_ACCESS_TEAM_DOMAIN` set and no AUD in scope it will refuse to run.

**Migrations must be backward compatible with the running code**, because they
apply before the restart. Adding a nullable column or a table is safe. Dropping
or renaming one is not — split that across two releases: deploy code that stops
using the column, then remove it in the next release.

### Verify

```bash
ssh fcf 'curl -s localhost:8000/api/health'
# expect: "status":"ok" AND accounts.status":"ok" AND auth_mode":"cloudflare"

ssh fcf 'curl -s -o /dev/null -w "stats=%{http_code}\n"  localhost:8000/api/v5/stats'
ssh fcf 'curl -s -o /dev/null -w "folders=%{http_code}\n" localhost:8000/api/v5/folders'
# expect: stats=200, folders=401

curl -s -o /dev/null -w "public=%{http_code}\n" https://fcf.drakesdev.com/
# expect: 302 (Access login) -- a 200 here would mean Access is not gating

ssh fcf 'journalctl -u fcf -n 20 --no-pager | grep -iE "error|critical|traceback"'
```

`auth_mode` reading anything but `cloudflare`, or `accounts.status` not `ok`,
means the environment did not load — check `EnvironmentFile` and restart.

After the frontend phase, confirm the browser is on the new code: the hash in
`https://fcf.drakesdev.com/` → view-source → `assets/index-<hash>.js` should
match `ls foundation-explorer/frontend/dist/assets/`.

### Rollback

The backend rolls back the same way it ships — there is no release history on
the box, so roll back in git and redeploy:

```bash
git revert <bad-sha>          # or: git checkout <good-sha> -- <paths>
# then re-run the backend release steps above
```

Faster, if the tree on the droplet is still good and only the process is
unhealthy: `ssh fcf 'systemctl restart fcf'`.

**A migration is the one thing that does not roll back cleanly.** `alembic
downgrade -1` works and revision `0001` has a tested `downgrade()`, but it drops
tables — running it against production destroys every saved folder. Restore from
the `pg_dump` instead:

```bash
gunzip -c fcf-<stamp>.sql.gz | ssh fcf 'sudo -u postgres psql -d fcf'
```

The frontend rolls back by rebuilding at the previous commit and re-running
phase 1. Because the old bundle is still on disk until pruned, this is fast.

### Toward zero downtime

Not implemented; recorded so the choice is deliberate rather than forgotten.

The 1.5 s gap exists because one uvicorn process owns `:8000` and nginx has a
single `proxy_pass` with no fallback. The smallest change that removes it:

1. Run two instances via a templated unit, `fcf@8000` and `fcf@8001`.
2. Give nginx an `upstream` block with both, plus
   `proxy_next_upstream error timeout http_502;` so a refused connection is
   retried against the sibling rather than surfaced.
3. Restart them one at a time, verifying health between.

Cost is a second ~475 MB process; the droplet has ~3.2 GB available, so it
fits. This only helps rolling code deploys — a migration that is incompatible
with the running code still needs the two-release split described above, and a
database refresh still restarts both.

Worth doing when deploys become frequent enough that 1.5 s matters, or when
someone other than the person deploying is relying on the site.

## Deploying the frontend

Two phases, in this order. Do **not** collapse them into one `rsync --delete`.

```bash
cd foundation-explorer/frontend
npm run build

# 1. New assets first, WITHOUT --delete. Filenames are content-hashed, so
#    these are additions and cannot collide with what is already live.
rsync -av \
  --exclude 'demo/' --exclude 'demo-v5/' --exclude 'sample/' --exclude 'report/' \
  dist/ fcf:/var/www/fcf/
```

Phase 1 also overwrites `index.html`, which is the cutover: the moment it
lands, new page loads reference the new bundle, which is already in place.

```bash
# 2. Later -- next day, or at least after every open tab has reloaded --
#    prune the superseded bundles.
ssh fcf 'ls -lt /var/www/fcf/assets/'      # confirm what is old
ssh fcf 'rm /var/www/fcf/assets/index-<OLDHASH>.js /var/www/fcf/assets/index-<OLDHASH>.css'
```

### Why not `--delete` in one shot

Vite content-hashes asset filenames, and `index.html` references them by hash.
A single `rsync --delete` removes the old bundle at the same moment it installs
the new one. Any browser still holding the previous `index.html` — a tab open
since before the deploy, or a cached copy — then requests
`assets/index-<oldhash>.js` and gets a **404 and a blank page**, until the user
thinks to hard-reload. That is a worse outage than a backend restart, because
it does not resolve itself.

Deploying additively leaves both bundles on disk, so old tabs keep working and
new loads get the new code. Disk cost is a few hundred KB.

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

See [Backend release](#backend-release) above — the commands live there so
there is one copy to keep correct.

Two things that section encodes and an ad-hoc `rsync` will not:

- **`--exclude 'venv/'`.** `/opt/fcf/venv` sits inside the rsync target, so
  `--delete` without it removes the interpreter mid-deploy.
- **`--exclude 'data/'`.** Keeps a code sync away from the 1.3 GB read model,
  which has its own procedure below.

After any restart, check `journalctl -u fcf -n 50`. A bad import fails at
startup, and `main_v5.py` raises deliberately if `explorer_v5.db` is missing.

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
copies of the db is ~3.7 GB of the 80 GB disk.

### The search index rides with the database

`/api/v5/search` reads FTS5 tables that live inside `explorer_v5.db`. A rebuilt
read model does not have them, so **every refresh must rebuild the index too**
or search returns 500s while the rest of the site looks healthy.

Either build it locally before shipping (`python3 -m src.build_search_index`,
~17 s, and the file grows 1.33 GB → 1.85 GB), or build it on the droplet
against a copy, which moves 500 MB less over the wire:

```bash
ssh fcf 'cd /opt/fcf && cp data/explorer_v5.db data/explorer_v5.db.new \
         && python3 -m src.build_search_index --db data/explorer_v5.db.new \
         && chown fcf:fcf data/explorer_v5.db.new'          # ~51 s on the box
ssh fcf 'ls /opt/fcf/data/explorer_v5.db.new-wal 2>/dev/null && echo REFUSE'
ssh fcf 'systemctl stop fcf \
         && mv /opt/fcf/data/explorer_v5.db.new /opt/fcf/data/explorer_v5.db \
         && systemctl start fcf'
```

`chown` matters: a file built as root is unreadable by the service user and
the API fails at startup. The `-wal` check is the rule from the project's
SQLite notes — sidecars follow the *filename*, so swapping a database that
still has one is how this project corrupted one before. `build_search_index`
checkpoints and drops the WAL before exiting precisely so this check passes.

Verify afterwards with `curl -s 'localhost:8000/api/v5/search?q=youth&limit=3'`
rather than only `/api/health`: health does not touch the FTS tables and will
report `ok` against a database that has none.

### The sector index rides with it too

`/api/v5/analytics/non-christian` and the cause breakdown in the detail panel
read `recipient_sectors` and `sector_stats`, built by
`src/build_sector_index.py`. Same rule as the search index: rebuild the read
model and they vanish.

**This one cannot be built on the droplet as things stand** — it needs
`data/bmf_registry.db` (852 MB), which is excluded from the code rsync and is
not on the box. So build both indexes locally, in this order, then ship the
finished database:

```bash
python3 -m src.build_search_index      # ~17 s, 1.33 GB -> 1.85 GB
python3 -m src.build_sector_index      # ~16 s, -> 1.93 GB, needs bmf_registry.db
```

Both refuse to run while anything else holds the database open, and both
checkpoint and drop the WAL before exiting.

Shipping 1.93 GB takes ~9 minutes at the ~3.7 MB/s this link measures. To let
rsync compute a delta instead, seed the target from the copy already on the
box:

```bash
ssh fcf 'cp /opt/fcf/data/explorer_v5.db /opt/fcf/data/explorer_v5.db.new'
rsync -av --inplace --progress data/explorer_v5.db \
      fcf:/opt/fcf/data/explorer_v5.db.new
```

`--inplace` is safe here only because `.new` is a scratch copy nothing is
reading. Never point it at the live file.

Then verify with an actual query, not just health:

```bash
curl -s 'localhost:8000/api/v5/analytics/non-christian' | head -c 200
```

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
