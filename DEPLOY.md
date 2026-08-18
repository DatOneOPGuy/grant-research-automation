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
| `/opt/fcf/data/explorer_v5.db` | ~1.33 GB read model, rsynced |
| `/opt/fcf/venv/` | `fastapi==0.139.0`, `uvicorn[standard]==0.49.0` |
| `/var/www/fcf/` | Built SPA (~500 KB) |
| `/etc/systemd/system/fcf.service` | The uvicorn unit |
| `/etc/nginx/sites-available/fcf` | TLS termination, `/api/` proxy, SPA fallback |

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
```

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
and must not be rsynced to `/var/www/fcf`.

## Security state

- No authentication. The site is fully public today.
- Planned gate: Cloudflare Access (Zero Trust, email policy). It protects the
  *hostname*, so it is not sufficient on its own — `ufw` must restrict `:443`
  to Cloudflare's published IP ranges, or `https://162.243.29.41` remains a
  direct bypass around the policy.
- SSH key rotation: new key installed, old key removed from `authorized_keys`
  and confirmed rejected. Outstanding: delete the old key from the DigitalOcean
  dashboard, check whether it is registered as a GitHub deploy key, and delete
  the local copies.

## Known gaps

- **No dependency pinning in version control.** `backend/requirements.txt` is
  two unpinned lines (`fastapi`, `uvicorn[standard]`). The `0.139.0` /
  `0.49.0` pins exist only inside the droplet's venv. Transitive deps float
  freely — starlette resolved to 1.6.0 on the box vs 1.3.1 locally. Generate a
  lockfile from the working venv (`pip freeze > requirements.lock`) and deploy
  from that.
- **Error copy names localhost.** Three strings tell production users to start
  a backend on `localhost:8000`: `pages/Dashboard.tsx:27`,
  `pages/Foundations.tsx:183`, `components/foundations/DetailPanel.tsx:164`.
- **Netlify remnants.** `foundation-explorer/frontend/netlify.toml` and
  `.netlify/` are still present; the SPA redirect they define is now nginx's
  `try_files`. Remove once the Netlify site is decommissioned.
- **Pending kernel reboot** on the droplet.
