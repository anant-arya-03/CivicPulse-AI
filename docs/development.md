# Local Development

> Status: **Milestone 6.** Everything below works today.

**VS Code tip:** pick the backend interpreter so imports resolve (Command Palette → *Python: Select Interpreter* → `backend/.venv`).

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Node.js | 20.9+ (22/24 recommended) | `node --version` |
| npm | 10+ | `npm --version` |
| Python | 3.11+ | `python --version` |
| PostgreSQL | 16+ **or** a free Supabase project | `psql --version` |
| Git | any recent | `git --version` |

You don't need Docker.

### Installing PostgreSQL locally

**Windows** (what this project's laptop uses). Open PowerShell and run:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --exact --silent --accept-package-agreements --accept-source-agreements `
  --override "--mode unattended --unattendedmodeui minimal --superpassword postgres_dev --serverport 5432 --disable-components stackbuilder"
```

Accept the Windows admin prompt. PostgreSQL then runs as the Windows service `postgresql-x64-17` and starts with your PC. The superuser is `postgres` / `postgres_dev` (a development password; change it on any shared machine). To use `psql`, add `C:\Program Files\PostgreSQL\17\bin` to your PATH.

- **macOS:** `brew install postgresql@17 && brew services start postgresql@17`
- **Ubuntu/Debian:** `sudo apt install postgresql && sudo systemctl start postgresql`

Then create the app user and the two databases (one for the app, one that tests may wipe):

```bash
psql -U postgres -h localhost -c "CREATE USER civicpulse WITH PASSWORD 'civicpulse_dev';"
psql -U postgres -h localhost -c "CREATE DATABASE civicpulse OWNER civicpulse;"
psql -U postgres -h localhost -c "CREATE DATABASE civicpulse_test OWNER civicpulse;"
```

These match the defaults in `.env.example`, so no other configuration is needed.

### Using Supabase instead

1. Create a project at supabase.com → **Connect** → copy the **Session pooler** or **Direct** connection string (port **5432**). Avoid the transaction pooler (port 6543): it doesn't work well with SQLAlchemy's prepared statements.
2. Change the scheme to `postgresql+psycopg://` and append `?sslmode=require`.
3. Put it in `DATABASE_URL` in `.env`. Keep `TEST_DATABASE_URL` pointing at a **local** database or a second project, because tests write to it.

## 2. One-command setup

From the repository root:

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
```bash
# macOS / Linux
bash scripts/setup.sh
```

The script:
1. creates `.env` from `.env.example` with a random `SECRET_KEY` (an existing `.env` is never overwritten),
2. creates `backend/.venv` and installs the Python packages,
3. runs the database migrations and creates the demo user,
4. runs `npm install` for the frontend.

It is safe to run again at any time.

## 3. Start the app

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1    # Windows: backend opens in a 2nd window
```
```bash
bash scripts/dev.sh                                          # macOS / Linux: Ctrl+C stops both
```

| URL | What |
|---|---|
| http://localhost:3000 | The website |
| http://localhost:8000/docs | Interactive API docs (Swagger UI) |
| http://localhost:8000/api/v1/health | Health check (`{"status":"ok","database":"ok"}`) |

**Demo login:** `demo@civicpulse.example` / `DemoPass123` (created by the seed script; development only).

### Doing it by hand (what the scripts run)

```bash
# Terminal 1: backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux
pip install -e ".[dev]"
alembic upgrade head                # create/upgrade tables
python -m scripts.seed              # demo user + fictional Demo City departments
uvicorn app.main:app --reload       # http://localhost:8000

# Terminal 2: frontend
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

## 4. Configuration

All settings live in the **repository-root `.env`** (template: `.env.example`) and are read by `backend/app/core/config.py`. The frontend needs nothing. Create `frontend/.env.local` with `BACKEND_URL=...` only if the API isn't at `http://localhost:8000`.

Key variables for Milestone 1:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Main database (`postgresql+psycopg://user:pass@host:5432/db`) |
| `TEST_DATABASE_URL` | Separate database for pytest. Must contain `test` in its name (a safety check). |
| `SECRET_KEY` | Signs CSRF tokens. Must be long and random; required in production. |
| `SESSION_TTL_HOURS` | How long a login lasts (default 168 = 7 days) |
| `COOKIE_SECURE` | `true` in production (HTTPS only cookies) |
| `LOCAL_STORAGE_DIR` | Where uploaded photos are kept (default `backend/storage/`, ignored by git) |
| `MAX_UPLOAD_MB` | Photo size limit (default 10). Keep `proxyClientMaxBodySize` in `frontend/next.config.ts` a little higher. |
| `GEOCODER` | `mock` (default: fictional "Demo City" sample places, works offline) or `nominatim` (real OpenStreetMap addresses) |
| `NOMINATIM_USER_AGENT` | Required for `nominatim`: your app name **and a real contact email**, e.g. `CivicPulseAI-student-project (contact: you@your-university.edu)`. The backend refuses to start without it. |

### AI settings

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `mock` (default: free, offline, labelled "Demo AI") or `anthropic` (real Claude) |
| `MOCK_AI_SCENARIO` | what the mock answers: `pothole`, `streetlight`, `garbage`, `not_civic`, `failure` (simulates an outage), `invalid` (simulates a broken answer) |
| `MOCK_AI_RESOLUTION` | what the mock says when comparing before/after photos (it doesn't look at them): `resolved` (default), `not_resolved`, `partial`, `unsure`, `different_place` |
| `ANTHROPIC_API_KEY` | required for `anthropic`. Server-side only; never put it in the frontend. |
| `AI_MODEL` | default `claude-opus-5-5` |
| `AI_EFFORT` | `low` / `medium` (default) / `high`: how much the model thinks before answering |
| `AI_TIMEOUT_SECONDS` | default 90 |

To use real Claude: create a key at console.anthropic.com, then set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...` in `.env`, and restart the backend. Every photo analysis and every AI letter is one billed API call; the backend limits each client to 10 AI calls per minute. To see the error screens, set `MOCK_AI_SCENARIO=failure` and restart.

### Email / submission settings

| Variable | Purpose |
|---|---|
| `EMAIL_PROVIDER` | `mock` (the only option): records a **simulated** submission and never contacts anyone |
| `MOCK_EMAIL_SCENARIO` | `success` (default), `failure` (every send fails: try the retry screen), `flaky` (the first attempt fails, the retry works) |
| `EMAIL_FROM_ADDRESS` | the "from" shown in the preview (default `civicpulse-demo@example.com`) |
| `ALLOW_REAL_SUBMISSIONS` | `false` (default). Safety guard for a future real provider: even then, nothing is sent to a demo department or a reserved `.example`/`.test`/`.invalid` address. Leave it off. |

### Follow-ups and the worker

| Variable | Purpose |
|---|---|
| `FOLLOWUP_FIRST_AFTER_DAYS` | wait this long for a first reply when the department lists no response time (default 7) |
| `FOLLOWUP_INTERVAL_DAYS` | wait between reminders (default 7) |
| `FOLLOWUP_MAX_COUNT` | reminders per complaint, at most (default 2); after that, escalation is recommended |
| `SCHEDULER_MAX_ATTEMPTS` | retries for a failing scheduled check (default 3) |
| `ENABLE_SIMULATION` | `true` only for development and demos: simulated replies, "skip ahead", and the worker's `--now`. **Must be false in production** (the backend refuses to start otherwise). |

The worker checks for missed deadlines and drafts reminders. **It never sends anything.** Run it by hand, or every 15 minutes with Windows Task Scheduler or cron (several copies at once are safe):

```bash
cd backend
python -m app.workers.run_pending                              # what is due now
python -m app.workers.run_pending --now 2026-12-01T10:00:00Z   # demo: pretend it is that date
```

For a demo in the browser, open a submitted complaint: the dashed **Demo tools** card can simulate a department reply (acknowledged, in progress, fixed, asks for information, declined, auto-reply, prompt-injection attempt) and **Skip ahead to the next check**.

### The department directory

The seed script adds a **fictional** directory for "Demo City" (country `XX`): roads, street lighting, waste, water/sewerage, storm-water drains (these two overlap on waterlogging and open drains, to show the "please choose" case), a commissioner's office (escalation only), and a state public works department. All use unreachable `@demo-city.example` addresses, and the UI labels them "Demo directory entry". Use a Demo City address (the mock geocoder's sample places are all there) to see a match.

Real departments are **never** included. To add ones you verified yourself, follow `docs/database.md` §4 (`python -m scripts.import_authorities file.json`, then `--apply`).

### Turning on real address search

Nominatim is free but has a [usage policy](https://operations.osmfoundation.org/policies/nominatim/): at most 1 request per second, an identifying User-Agent, and no autocomplete. The backend enforces the first two, and the UI only searches when you press **Search**. In `.env`:

```bash
GEOCODER=nominatim
NOMINATIM_USER_AGENT=CivicPulseAI-student-project (contact: you@your-university.edu)
```

Restart the backend afterwards. Map tiles always come from OpenStreetMap (an internet connection is needed to see the map).

## 5. Database migrations

```bash
cd backend   # with the venv active
alembic upgrade head                               # apply all migrations
alembic revision --autogenerate -m "add complaints" # create a migration from model changes
alembic downgrade -1                               # undo the last migration
alembic history                                    # list migrations
```

Always open and read a generated migration before applying it. Also add any new `models.py` import to `backend/app/models.py`, or autogenerate won't see the table.

## 6. Tests and checks

```bash
# Backend (from backend/, venv active)
pytest                      # 470 tests; uses TEST_DATABASE_URL, every test rolled back (no real AI or email)
ruff check . && ruff format --check .

# Frontend (from frontend/)
npm run test                # Vitest unit/component tests
npm run lint                # ESLint
npm run typecheck           # TypeScript
npm run build               # production build (also validates Next.js rules)

# End-to-end (from frontend/). Starts both servers if they aren't running.
npx playwright install chromium   # first time only (~150 MB download)
npm run test:e2e                  # 18 tests: desktop + mobile, 2 at a time (about 1.5 minutes)
```

**Tip for e2e:** stop your own dev servers first. Playwright then starts fresh ones with rate limiting off, simulation on, and the mock geocoder, AI (`pothole`), and email (`success`). Don't run `npm run build` right before e2e: a production `.next` folder makes the dev server slow enough to time out. Delete `frontend/.next` after building. Before the tests, `e2e/global-setup.ts` requests every page once so the dev server compiles them; the tests run two browsers at a time, because with more, `next dev` gets too slow on a laptop and long journeys time out. Shared helpers (register, submit a complaint through the API, simulate a reply) live in `e2e/helpers.ts`. If you keep yours running, it reuses them, and quick repeated runs can hit the login/register rate limit.

The e2e tests use the **development** database and create users named `e2e-…@civicpulse.example`. Delete them whenever you like:
`psql -U civicpulse -h localhost -d civicpulse -c "DELETE FROM users WHERE email LIKE 'e2e-%' OR email LIKE 'smoke-%';"`

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `psql: command not found` (Windows) | Add `C:\Program Files\PostgreSQL\17\bin` to PATH, then reopen the terminal. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or run scripts with `-ExecutionPolicy Bypass`. |
| `password authentication failed` | Check the user and password in `DATABASE_URL`; special characters must be URL-encoded. |
| `connection refused :5432` | PostgreSQL isn't running. Windows: `Start-Service postgresql-x64-17` (admin). |
| `TEST_DATABASE_URL must be a separate database…` | Point it at `civicpulse_test`, never at your main database. |
| Supabase `prepared statement … already exists` | You used the transaction pooler (6543); switch to session/direct (5432). |
| Website loads but every action fails / health shows 500 | The backend isn't running, or `BACKEND_URL` is wrong. |
| Every POST returns `CSRF_FAILED` | Clear the site's cookies and log in again. The API client sends `X-CSRF-Token` automatically. |
| `Too many attempts` on login | Rate limit (10/min per IP). Wait a minute or restart the backend. |
| Port 3000 or 8000 already in use | Stop the other process, or run `npm run dev -- -p 3001` / `uvicorn ... --port 8001` (then set `BACKEND_URL`). |
| Dev server (and e2e tests) suddenly 3× slower, tests time out on `toHaveURL` | You ran `npm run build` earlier; its output in `frontend/.next` slows `next dev` down. Stop the dev server, delete the `frontend/.next` folder, and start it again. |
| `Another next dev server is already running` / e2e fails with strange "worker" errors | A dev server from an interrupted test run is still alive. It prints its PID; stop it with `taskkill /PID <pid> /F` (Windows) or `kill <pid>`. |
| Backend won't start: `AI_PROVIDER=anthropic needs ANTHROPIC_API_KEY…` | Add the key to `.env`, or set `AI_PROVIDER=mock`. |
| Step 2 always says "AI analysis isn't available" | With `mock`: check `MOCK_AI_SCENARIO` isn't `failure`/`invalid`. With `anthropic`: check the key and your internet connection; the backend log shows the error code. |
| Backend won't start: `GEOCODER=nominatim needs NOMINATIM_USER_AGENT…` | Put your own contact email in `NOMINATIM_USER_AGENT`, or set `GEOCODER=mock`. |
| Photo upload says "HEIC photos aren't supported" | iPhones save HEIC by default. Export as JPEG, or set the camera to "Most Compatible". |
| The map shows only blue water | You're using the mock geocoder: its fictional "Demo City" sits at sea near 0°, 0°. Switch to `nominatim` for real places. |
| Migration error `Can't locate revision …` in tests | The test database has an old migration recorded. Reset it: `psql -U civicpulse -h localhost -d civicpulse_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"` |
