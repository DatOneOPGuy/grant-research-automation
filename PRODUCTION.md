# Foundation Explorer — Production State

**Snapshot taken 2026-08-22.** This describes what is running. For *how* to
deploy, change or refresh it, see [DEPLOY.md](DEPLOY.md); this file is the
current-state companion to that procedure.

---

## What the product is

Foundation Explorer is a prospect-research tool over US private foundation
990-PF filings, aimed at fundraisers looking for Christian-aligned funders.

The pipeline ingests IRS filings, resolves recipient identities, and
classifies giving by religious tradition with an evidence trail. The Explorer
is the web front end over the resulting read model:

| | |
|---|---|
| Foundations | 123,113 |
| Recipients | 1,302,051 |
| Paid grants covered | $236.4 B, tax years 2023–2024 |
| Christian-attributed | $11.5 B |
| Foundations with mission text | 46,671 |

Nine pages: dashboard, best prospects, the main foundations table with
composable filters, a grants explorer, recipients, analytics, data quality, a
trust/methodology page, and **Saved** — team-shared folders of prospects.

The product's honesty rules are load-bearing, not cosmetic. Aggregates are
computed over the full database; `pct_christian` stays NULL where nothing
could be classified rather than being coerced to 0%, because 0% would assert
the giving is non-Christian.

---

## Live deployment

**https://fcf.drakesdev.com** — DigitalOcean droplet `162.243.29.41`
(Ubuntu 24.04.4, 4 GB / 80 GB, NYC2), ssh alias `fcf`.

```
Browser
   │
   ▼
Cloudflare Access ─── One-time PIN, policy "FCF team"
   │                  (adds Cf-Access-Jwt-Assertion to every request)
   ▼
nginx :443  ── TLS (certbot) ── ufw: only Cloudflare ranges may reach :443
   ├── /            → /var/www/fcf          static SPA, try_files → index.html
   └── /api/        → 127.0.0.1:8000        uvicorn
                          │
                          ├── v5.router      13 GETs   → explorer_v5.db (SQLite, read-only)
                          └── folders.router  8 routes → Postgres (accounts, all authenticated)
```

Single FastAPI process, two routers. The read path and the write path share
nothing but the port.

### Host layout

| Path | Contents |
|---|---|
| `/opt/fcf/` | The repo, **rsynced** from the laptop — not a clone, no deploy key |
| `/opt/fcf/data/explorer_v5.db` | 1.3 GB read model, rsynced. Rebuildable |
| `/opt/fcf/venv/` | Python 3.12.3, installed from `backend/requirements.lock` |
| `/var/www/fcf/` | Built SPA, 500 KB |
| `/etc/fcf/fcf.env` | Service environment, `640 root:fcf` |
| `/etc/systemd/system/fcf.service` | uvicorn unit + `EnvironmentFile` |
| `/etc/nginx/sites-available/fcf` | TLS, `/api/` proxy, SPA fallback |
| Postgres 16.15, localhost only | Accounts and shared folders. **Not** rebuildable |

Disk: 4.4 GB of 77 GB used.

### Two datastores, opposite properties

`explorer_v5.db` is a compiled artifact — if it is lost, rebuild it from the
pipeline. It carries inline DDL and no migration history because it is
recreated wholesale.

Postgres holds folders and notes people typed. It exists nowhere else and
cannot be regenerated, which is why it gets Alembic and why a `pg_dump`
before any migration is worth the thirty seconds.

---

## Identity and authorisation

**Cloudflare Access is the identity provider.** It authenticates the user
before the request reaches the origin and forwards a signed JWT. The
application verifies that token against Cloudflare's JWKS and trusts the email
inside. No passwords, sessions, or reset flows are stored here.

- Team domain `shy-thunder-37cd.cloudflareaccess.com`, issuer
  `https://shy-thunder-37cd.cloudflareaccess.com`, audience pinned to the
  `fcf` application's AUD tag.
- Accounts are created on first sight of a verified email — no invite flow,
  because Access already decided who gets through.
- **Folders are shared across the team, not private per user.** Everyone sees
  and edits the same folders; `created_by` / `added_by` are attribution, not
  access control. Prospect research is a team activity and a list only its
  author can see is a list the team cannot act on.
- Every folder query filters on the caller's `team_id`, in a single helper.
  Another team's folder id returns **404, not 403** — a 403 would confirm the
  id exists and allow enumeration.
- One team today. `team_id` is on every table, so a second team is a data
  change rather than a migration.

### Current accounts

| | |
|---|---|
| Teams | 1 — "Foundation Explorer" |
| Users | 4 |
| Folders | 3 |
| Saved items | 1 |

`drake.lesher@gmail.com`, `lesherda@wofford.edu`, `info@flagshipequip.com`,
`mr.frace@gmail.com` — all on team 1. The account system is in real use;
saved folders persist server-side and are shared.

### Fail-closed properties

- A missing, malformed, expired, wrong-issuer or wrong-audience token is a
  401. The reason goes to the log, never to the client.
- A token with no `email` claim (a service token) is refused rather than
  mapped onto a synthetic account.
- **The process refuses to boot** if `DEV_USER_EMAIL` is set alongside either
  `CF_ACCESS_*` variable. The dev bypass mints sessions without checking a
  token, so the dangerous combination is unbootable rather than merely
  discouraged.
- **No team row is ever created at runtime.** An earlier version created one
  lazily; eight concurrent first-logins against an empty table produced six
  teams and silently partitioned the users. A missing team row now logs
  CRITICAL and returns 503.

---

## Degradation behaviour

Postgres being unreachable **degrades, it does not kill**:

- all 13 read routes keep serving
- folder endpoints return 503, never 500
- `/api/health` reports it

```json
{"status": "ok",
 "model": "/opt/fcf/data/explorer_v5.db",
 "accounts": {"status": "ok", "auth_mode": "cloudflare"}}
```

`status` becomes `degraded` when Postgres is down. A monitor checking only the
HTTP status code will miss that — **alert on `accounts.status`**. `auth_mode`
must read `cloudflare` in production.

Migrations are an explicit deploy step and never run at startup: a process
that migrates on boot turns a restart into a schema change, and a crashloop
into that schema change attempted several times a second.

---

## Security posture

**Closed:**

- **The origin bypass.** `ufw` now permits `:443` only from the 15 published
  Cloudflare IPv4 ranges. `https://162.243.29.41/api/v5/stats` no longer
  connects — previously it served the entire compiled database with no login,
  which was the single largest exposure and a LICENSE-LIFETIME §2 breach.
- Port 80 is open to the world but only `301`s to HTTPS, where ufw applies. No
  data path.
- Postgres binds to localhost only.
- Credentials live in `/etc/fcf/fcf.env` at `640 root:fcf` — readable by the
  service user, denied to others, absent from the unit file and the repo. The
  password was generated on the droplet and has never been on the laptop.
- TLS valid to 2026-11-16 (85 days), certbot auto-renew configured.
- Kernel reboot completed; no pending reboot.
- Dependencies pinned. `requirements.lock` fixes the full resolved set,
  including `starlette==1.6.0` — the transitive that was drifting between the
  laptop and the droplet.

**Open:**

- **Reads are unauthenticated at the application layer.** The 13 GETs are
  deliberately untouched, so Cloudflare Access plus the ufw lock are the only
  things gating the dataset. Those two are now doing real work rather than
  being decorative, but a Cloudflare misconfiguration would expose everything
  again. Only the account endpoints check a token.
- **No IPv6 rule for `:443`.** Fine today, since Access reaches the origin
  over IPv4. Adding an AAAA record would break the site until matching
  Cloudflare IPv6 ranges are allowed.
- **Cloudflare's IP ranges are pinned by hand.** They change occasionally;
  nothing here refreshes them, and the failure mode is the site going dark.
- **No Postgres backup schedule.** `pg_dump` is manual.
- SSH key rotation: the old key was removed from `authorized_keys` and
  confirmed rejected. Still to do: delete it from the DigitalOcean dashboard
  and check whether it is a GitHub deploy key. (It is *not* in this repo —
  not tracked, not in history, not on disk.)

---

## Verified

Confirmed against the live deployment:

- all 13 read routes return 200
- `/api/health` reports `accounts.status: ok`, `auth_mode: cloudflare`
- `/api/v5/folders` and `/api/v5/me` return 401 with no token, and with a
  malformed one
- through Cloudflare, `/` and `/api/v5/folders` both 302 to login
- the origin IP refuses `:443` from outside Cloudflare
- the deployed SPA calls the API and contains **no** reference to the old
  `fe.saved.v2` localStorage key — `LocalSavedStore` is tree-shaken out of the
  production bundle, so there is no code path by which a save could silently
  persist nowhere
- cross-team isolation, on every endpoint taking a folder id
- droplet backend files match the local repo by md5; deployed bundle matches
  `dist/`; working tree clean at `2a5f029`, level with `origin/llama`

**Tests:** 41 account/identity tests (cross-team isolation, real RS256 tokens
through the real auth path, the JWKS client built unstubbed, the concurrent
first-login race) plus 19 pipeline tests. The account tests need a Postgres
via `TEST_DATABASE_URL` and skip without one.

---

## Version

Branch `llama` at `2a5f029`. Recent history:

```
2a5f029  Fix the JWKS client: lifespan=0 made every login fail
83c1564  Document the Postgres and Access setup in DEPLOY.md
71fd239  Move saved folders from localStorage to the team's account
da52518  Authenticate with Cloudflare Access and serve shared folders
bbf67ac  Add the accounts schema: teams, users, folders, folder items
0e6c2f5  Export every Christian-giving foundation to the demo dataset
8ca7c08  Search foundations by name or EIN
721d526  Serve the live API in production instead of the static demo
```

Alembic at `0001_accounts (head)`, no drift.

Not merged to `main`. This branch is what production runs.
