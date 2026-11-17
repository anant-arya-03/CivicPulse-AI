# AGENTS.md — CivicPulse AI handbook for coding agents

This file is the starting point for Codex, Claude Code, or any other AI coding agent (and for new human contributors). Read it fully before changing anything. It explains what the project is, how it is built, the rules that must never be broken, and step-by-step recipes for common changes. Human-facing overview: [README.md](README.md). Deep references: [docs/](docs/).

---

## 1. What this project is

**CivicPulse AI** is a civic complaint platform:

1. A citizen photographs a public infrastructure problem (pothole, broken streetlight, garbage, open drain, water leak, waterlogging).
2. **AI suggests** the issue type, title, description and a cautious severity (Vision agent). The citizen edits.
3. The citizen enters and confirms the **location** (never inferred from the photo).
4. A **department** is matched from a source-backed directory by deterministic code (never invented by AI).
5. **AI drafts** a formal letter; facts come from the database via a template.
6. The citizen **approves the exact message** (SHA-256 content hash) and it is **sent (simulated)**, idempotently.
7. Department **replies** (simulated in development) are read by the Monitoring agent; **fixed rules** decide status changes; reference numbers are kept only if they appear verbatim.
8. If there is no reply by the deadline (the department's listed response time, or a default), a **worker drafts a reminder**: never sent automatically, at most 2, each approved. Then escalation contacts from the directory are suggested.
9. When the department says it's fixed, the citizen uploads an **after photo**; the Resolution agent compares before/after **as advice**; **only the citizen** confirms (`VERIFIED_RESOLVED`) or disputes (`REOPENED` + a "not fixed" message draft).

Core principle, everywhere: **AI suggests → fixed backend rules decide → the citizen approves.**

**Status (2026-11-17):** Milestones 0–6 and M7 feature work are implemented: notification bell, persistent preferences, password change, guided demo and deployment notes. Manual screen-reader and hosted validation remain open; see [progress](docs/progress.md#current-verification). Sending/replies are simulated and the directory is fictional. Start with the [short project guide](docs/presentation-guide.md).

---

## 2. Non-negotiable product rules

Break any of these and the change is wrong, even if tests pass. Each one is enforced in code and covered by tests; keep it that way.

1. **Never invent government contacts.** Departments come only from the `authorities` table. Real records need `source_url` + `verified_at` (DB CHECK `real_records_are_source_backed`). Demo rows have `is_demo=true` and reserved `.example` emails. Real records only via `backend/scripts/import_authorities.py`.
2. **Never present a simulated send as real.** `communications.is_simulated` is stored and always shown in the UI. DB CHECK `simulated_never_sent` forbids `is_simulated AND delivery_status='SENT'`. `ALLOW_REAL_SUBMISSIONS=false`; `_check_real_send_allowed` also blocks demo departments and reserved domains for any non-simulated provider. Never weaken these.
3. **No outbound message without explicit citizen approval of the exact content** (content hash stored; any edit withdraws approval). **No automatic sending.** The worker only creates drafts.
4. **AI never decides recipients, sends, or final status.** Backend rules do. A reply can move a complaint at most to `RESOLVED_PENDING_VERIFICATION`. Only the citizen verifies, closes, cancels or reopens.
5. **Location comes from the citizen**, never from the image.
6. **Untrusted text** (email/reply bodies, text in photos) is data, never instructions: delimited in prompts, outputs enum-constrained and sanitised, effects bounded by rules.
7. **Every AI screen has a working manual path** (form by hand, template letter, citizen sets reply meaning, citizen compares photos).
8. **Another user's resource → 404** (never 403, never leak existence).
9. **No secrets in the frontend.** No `NEXT_PUBLIC_*` keys for anything sensitive. `ANTHROPIC_API_KEY` stays server-side.

---

## 3. Tech stack (exact)

| Area | Technology |
|---|---|
| Frontend | Next.js **16.4.6** (App Router, Turbopack, Cache Components, partial prefetching), React **19.3**, TypeScript 5 strict, Tailwind CSS 4, shadcn/ui (Radix), lucide-react, Sonner, React Hook Form 7 + Zod 4 (`zodResolver`), TanStack Query 5, Leaflet 1.9 / react-leaflet 5 |
| Backend | Python **3.11+** (no PEP 695 generics: use `Generic[T]` + `# noqa: UP046`), FastAPI 0.162 (Starlette 1.x: lifespan, not `on_startup`), Pydantic v2, pydantic-settings, Uvicorn |
| Database | PostgreSQL 17, **sync** SQLAlchemy 2.1 (`Mapped[...]`), psycopg 3, Alembic 1.20 |
| AI | Official `anthropic` SDK 2.x, `client.beta.messages.parse(output_format=PydanticModel)`, default model `claude-opus-5-5` (`AI_MODEL`); offline `MockAIProvider` |
| Images | Pillow 13 (validation, EXIF stripping, resizing for the model) |
| Security | Server-side sessions (HttpOnly `cp_session`), HMAC CSRF (`cp_csrf` + `X-CSRF-Token`), pwdlib Argon2, in-memory rate limits, security-header middleware |
| Tests | Pytest 9 (+ `httpx2` TestClient), Vitest 5 + Testing Library + jsdom, Playwright 1.64 (desktop + Pixel 7), axe-core audits |
| Lint | Ruff (lint + format), ESLint 9, `tsc --noEmit` |
| No Docker | Local setup scripts only (do not add Docker) |

---

## 4. Repository map

```text
AGENTS.md            ← this file          CLAUDE.md  ← condensed conventions (same rules)
README.md            ← showcase overview  .env.example ← every setting (copy to .env)
scripts/             setup.ps1|sh (once), dev.ps1|sh (run both servers)
docs/                architecture, database, api, workflows, design-system, development, progress,
                     screenshots/, authorities.example.json, CivicPulse-AI-presentation.pptx
backend/
  app/main.py                 FastAPI app: CSRF dependency, CORS, upload-limit + security-header middleware
  app/api_router.py           registers every module router under /api/v1   ← add new routers here
  app/models.py               imports every ORM model (Alembic needs it)     ← add new models here
  app/core/                   config.py (Settings), database.py (DbSession), security.py, errors.py,
                              rate_limit.py (RateLimit), upload_limit.py, security_headers.py
  app/common/                 time.py (utc_now), models.py (UUID PK + timestamps mixins), pagination.py
  app/integrations/           ai_providers/ email_providers/ storage/ geocoding/  (interface + mock + factory)
  app/modules/<feature>/      router.py (HTTP only) → service.py (rules) → models.py; schemas.py; constants.py
    auth, users               sessions, CSRF, profile, preferences, password/session revocation
    notifications             event-derived feed and sequence-based seen cursor
    complaints                complaints + timeline events, status_machine.py, dashboard
    evidence                  photo upload/validation/serving (ORIGINAL + FOLLOWUP)
    locations                 address search via geocoder
    ai                        agents/, prompts/ (versioned), schemas (AI outputs), sanitize, letter_template,
                              followup_template, image_prep, models (ai_analyses), service (records every call)
    authorities               directory, matcher.py (pure, deterministic), demo_data, importer schema
    communications            preview, approve (hash), idempotent send, reminders edit/approve/dismiss, hashing.py
    monitoring                rules.py (pure), scheduled_actions model, replies, worker logic, escalation,
                              dashboard attention, simulation (dev only)
    resolutions               rules.py (pure), resolution_reviews model, compare, decide, reopen
  app/workers/run_pending.py  runs due scheduled actions once (drafts only)
  alembic/versions/           migrations (review every autogenerated file; CHECK changes are manual)
  scripts/seed.py             demo user + Demo City directory;  scripts/import_authorities.py (verified records)
  tests/                      pytest (conftest: migrated test DB, every test rolled back, mock providers)
frontend/
  next.config.ts              /api/v1 rewrite → backend, 12 MB proxy body limit, security headers
  src/proxy.ts                Next 16 "middleware": redirect to /login for app pages
  src/app/                    thin routes: (marketing)/, (auth)/login|register, (app)/dashboard|report|complaints|settings
  src/features/<domain>/      api.ts, hooks.ts, schemas.ts, components/
    complaints/               report-wizard/ (6 steps), components/ (detail view, response-tracking,
                              repair-check, demo-tools), constants.ts (labels/icons/colours),
                              ai-suggestions.ts, submission.ts, monitoring.ts, resolution.ts
  src/components/             presentational pieces (ui/ = shadcn, shared/, complaints/, layout/)
  src/lib/                    api-client.ts (fetch + CSRF + ApiError + uploadFile), hydration.ts, format.ts
  src/types/api.ts            TypeScript mirrors of backend schemas
  e2e/                        Playwright specs, helpers.ts, global-setup.ts (warms dev server), fixtures/
```

---

## 5. Setup and commands

Prerequisites: Node.js 20.9+, Python 3.11+, PostgreSQL 16+ (built on 17). Databases: `civicpulse` (dev) and `civicpulse_test` (tests; name must contain `test`). App DB user `civicpulse` / `civicpulse_dev` (local only). Windows service: `postgresql-x64-17`.

```bash
# one-time (from repo root)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # Windows
bash scripts/setup.sh                                          # macOS/Linux
# run both servers
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1       # or: bash scripts/dev.sh
```

| Task | Command (backend from `backend/`, venv python on Windows is `.venv/Scripts/python`) |
|---|---|
| Backend server | `uvicorn app.main:app --reload --port 8000` (docs: http://localhost:8000/docs) |
| Migrate | `alembic upgrade head` · new: `alembic revision --autogenerate -m "msg"` · check drift: `alembic check` |
| Seed demo data | `python -m scripts.seed` (demo user `demo@civicpulse.example` / `DemoPass123`) |
| Backend tests | `pytest` (475 last recorded passing; see dated progress) |
| Backend lint | `ruff check . && ruff format --check .` |
| Worker | `python -m app.workers.run_pending [--now 2026-12-01T10:00:00Z]` (`--now` needs `ENABLE_SIMULATION=true`) |
| Frontend server | `npm run dev` (from `frontend/`; http://localhost:3000) |
| Frontend unit tests | `npm run test` (119 Vitest) |
| Frontend checks | `npm run lint && npm run typecheck && npm run build` (then **delete `frontend/.next`** before e2e) |
| End-to-end | `npm run test:e2e` (22 listed cases; starts servers if ports 3000/8000 are free; 2 workers) |

Key settings (root `.env`, read by `backend/app/core/config.py`): `AI_PROVIDER=mock|anthropic`, `ANTHROPIC_API_KEY`, `AI_MODEL`, `MOCK_AI_SCENARIO`, `MOCK_AI_RESOLUTION`, `EMAIL_PROVIDER=mock`, `MOCK_EMAIL_SCENARIO=success|failure|flaky`, `ALLOW_REAL_SUBMISSIONS=false`, `GEOCODER=mock|nominatim` (+ `NOMINATIM_USER_AGENT` with a real contact), `FOLLOWUP_FIRST_AFTER_DAYS`, `FOLLOWUP_INTERVAL_DAYS`, `FOLLOWUP_MAX_COUNT`, `SCHEDULER_MAX_ATTEMPTS`, `ENABLE_SIMULATION` (refused in production), `RATE_LIMIT_ENABLED`, `APP_ENV`.

---

## 6. Domain model

### Complaint statuses (single source of truth: `backend/app/modules/complaints/status_machine.py`)

| From | Allowed to |
|---|---|
| DRAFT | PENDING_REVIEW, CANCELLED |
| PENDING_REVIEW ("Ready to send") | DRAFT, SUBMITTED, CANCELLED |
| SUBMITTED | ACKNOWLEDGED, IN_PROGRESS, RESOLVED_PENDING_VERIFICATION, CLOSED, CANCELLED |
| ACKNOWLEDGED | IN_PROGRESS, RESOLVED_PENDING_VERIFICATION, CLOSED |
| IN_PROGRESS | RESOLVED_PENDING_VERIFICATION, CLOSED |
| RESOLVED_PENDING_VERIFICATION | VERIFIED_RESOLVED, REOPENED |
| VERIFIED_RESOLVED | CLOSED, REOPENED |
| REOPENED | ACKNOWLEDGED, IN_PROGRESS, RESOLVED_PENDING_VERIFICATION, CLOSED |
| CLOSED | REOPENED |
| CANCELLED | (terminal) |

Status groups (`complaints/constants.py`): `EDITABLE_STATUSES` = DRAFT, PENDING_REVIEW · `MONITORED_STATUSES` = SUBMITTED, ACKNOWLEDGED, IN_PROGRESS, REOPENED (reminders possible) · `VERIFIABLE_STATUSES` = MONITORED + RESOLVED_PENDING_VERIFICATION (after-photos and decisions allowed).

### Tables (details: [docs/database.md](docs/database.md))
`users`, `user_sessions`, `complaints` (+ `public_reference` like `CP-2026-000123`), `complaint_events` (timeline, ordered by `seq`), `evidence` (ORIGINAL/FOLLOWUP photos), `ai_analyses` (every AI call), `authorities` (directory), `communications` (outbound complaint/reminders, inbound replies; ordered by `seq`), `scheduled_actions` (worker queue), `resolution_reviews` (repair checks, audit trail).

Conventions: UUID PKs; `TIMESTAMPTZ` in UTC via `app.common.time.utc_now()` (never `datetime.now()`); enums stored as VARCHAR + Python `StrEnum` + DB CHECK; Windows clock is coarse, so **never order by timestamp alone** (use `seq` or `public_reference`).

---

## 7. Backend rules (how to write code that fits)

- **Layering:** `router.py` is HTTP only (parse, call service, return schema). Business rules live in `service.py`. Routers never query the DB. Cross-module access goes through the other module's **service** (models may be imported directly when needed to avoid cycles; lazy imports are used, with a comment, where modules depend on each other: e.g. `complaints.service._stop_monitoring`).
- **Route signatures:** use `DbSession` and `CurrentUser` (Annotated dependencies). CSRF is enforced globally by `verify_csrf`; never add per-route CSRF code. Rate-limit sensitive routes with `dependencies=[Depends(RateLimit("scope", times=N, seconds=S))]`.
- **Loading a complaint:** `complaint_service.get_owned_complaint(db, user, id)` (404 for others) or `get_editable_complaint`.
- **Status changes ONLY via** `complaint_service.change_status(db, complaint, new_status, event_type=..., description=..., actor=...)`; it validates with the status machine and writes a `complaint_events` row in the same transaction. Other timeline entries: `record_event(...)`. Next-step buttons come from `available_actions(complaint)`.
- **Errors:** raise from `app/core/errors.py` (`NotFoundError`, `ConflictError`, `BusinessRuleError`, `InvalidTransitionError`, `FileRejectedError`, `FileTooLargeError`, `RateLimitedError`, `ServiceUnavailableError`, `AIUnavailableError`, `SubmissionFailedError`, `RealSubmissionBlockedError`). The global handler returns `{"error": {"code", "message", "details"}}`.
- **Files:** only through the `get_storage` dependency (`StorageService`); photos only through `evidence.image_validation.validate_and_clean_image`. Save the file before commit, delete it on rollback.
- **AI:** agents call only `AIProvider.generate_structured(...)` (provider from `get_ai_provider`). Outputs are Pydantic models whose strings pass through `sanitize_ai_text` (see `ai/schemas.py` `_clean_text`/`_clean_list`). Record every call in `ai_analyses` via `ai/service.py` (`_record_success` / `_record_failure`; the caller commits). Prompts are versioned files `ai/prompts/<name>_vN.py`: **to change wording, add a new version**. AI never writes complaint fields directly; letters are replaced only with `replace_existing`; facts come from `letter_template.py` / `followup_template.py`.
- **Sending:** `communications.service.approve` (complaint) / `approve_followup` (reminder) store the content hash; `send` locks the row, re-checks rules, sets `SENDING` before calling the provider, uses a unique idempotency key. Anything that changes what would be sent must call `complaint_service.withdraw_approval`.
- **Monitoring:** decisions in `monitoring/rules.py` (pure; extend its tests). Replies enter only via `monitoring.service.receive_reply`; meanings are applied by `_apply_reply_kind` (AI only if confidence ≠ LOW; else the citizen via `classify_reply_manually`). Schedule with `schedule_check` (one per message, unique key); stop with `stop_monitoring` whenever a complaint stops waiting. Worker: `run_due_actions` (SKIP LOCKED, retries with back-off, stuck-run recovery). Scheduled actions never send.
- **Resolution:** allowed decisions in `resolutions/rules.py` (`transitions_for`, `cautions`). Only `resolutions.service.decide` / `reopen` change status after a repair claim; the AI comparison is stored as advice (`ai_assessment`). After-photos only via `evidence.service.upload_followup_evidence`. Reviews are never deleted.
- **Directory:** match with `authorities/matcher.py` (`match_authorities`, pure); set the department only with `authorities.service.select_authority`.
- **Integrations:** only through interfaces + factories in `app/integrations/`. Mock implementations must keep working without credentials.
- **New router → register in `app/api_router.py`. New models file → import in `app/models.py`.**

## 8. Frontend rules

- **Next.js 16 differs from older versions.** Read `frontend/node_modules/next/dist/docs/` before using an unfamiliar API (see `frontend/AGENTS.md`). Middleware is `src/proxy.ts`.
- **Server Components must not read cookies/session.** Authenticated pages are client components using TanStack Query; `AppShell` handles 401 → `/login`.
- **Wrap every `useQuery` in `useHydrationSafeQuery`** (`src/lib/hydration.ts`). Interactive prerendered inputs (file inputs, forms) must not lose input before hydration: disable until `useHydrated()`, or use `method="post"` on forms.
- `useSearchParams`, `useParams`, `usePathname` need a `<Suspense>` parent.
- **All API calls go through `src/lib/api-client.ts`** (adds `X-CSRF-Token`, parses errors into `ApiError`), using relative `/api/v1/...` paths. Uploads: `uploadFile` (XHR with progress).
- Structure: `app/` routes stay thin; `features/<domain>/` holds `api.ts`, `hooks.ts`, `schemas.ts`, components; `components/` holds presentational pieces. Types mirror the backend in `src/types/api.ts`.
- Forms: React Hook Form + Zod 4 (`zodResolver`); validation must match the backend (e.g. password 8–128 chars with a letter and a number; letter subject 5–200, body 20–10,000).
- AI suggestions go through `planSuggestions` (`features/complaints/ai-suggestions.ts`): fill empty fields only, offer the rest. Mock results show `AiSourceBadge` ("Demo AI").
- Labels, icons, status colours: `features/complaints/constants.ts`; delivery labels: `DELIVERY_META` / `deliveryLabel` (`submission.ts`); reply meanings: `monitoring.ts`; resolution labels: `resolution.ts`.
- Leaflet only via `components/complaints/location-map-loader.tsx` (client-only dynamic import). Evidence images use `EvidenceImage` (plain `<img>`, needs the session cookie, lazy).
- Layout: single-column grids that may contain wide media use `grid-cols-1`; items in `overflow-x-auto` strips need `relative`; no horizontal page scroll at 320–412 px.
- Design: Tailwind v4 tokens in `src/app/globals.css` ([docs/design-system.md](docs/design-system.md)). Primary buttons are navy (white-on-teal fails contrast); teal for accents. Keep axe-core at **0 violations** (contrast ≥ 4.5:1, landmarks, labelled regions, keyboard-reachable scroll areas).

---

## 9. Recipes for common changes

**Add an API endpoint**
1. Schema in `modules/<m>/schemas.py`; logic in `service.py` (ownership via `get_owned_complaint`, domain errors, `record_event`/`change_status`).
2. Thin route in `router.py` with `CurrentUser`, `DbSession`, and a `RateLimit` if sensitive. New router → `app/api_router.py`.
3. Tests in `backend/tests/` (happy path, 404 for another user via the `other_client` fixture, invalid input 422, rule violations 409/422).
4. Frontend: type in `src/types/api.ts`, call in `features/<m>/api.ts`, hook in `hooks.ts` (invalidate `complaintKeys.all` and `complaintKeys.dashboard` after mutations).
5. Update `docs/api.md`.

**Add or change a database column**
1. Edit the model (use `Mapped[...]`; enums as VARCHAR + CHECK).
2. `alembic revision --autogenerate -m "..."`, then **read the file**: autogenerate misses CHECK constraint changes; add `op.drop_constraint` / `op.create_check_constraint` by hand, with a working `downgrade()`.
3. `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`, `alembic check` (must say no new operations).
4. Update `docs/database.md`.

**Add a complaint category**
`complaints/constants.py` (`Category` + `CATEGORY_LABELS`) → `frontend/src/features/complaints/constants.ts` (label/icon) → `ai/prompts` (new prompt version listing it) → `letter_template.py` requested action → departments' `supported_categories`.

**Change an AI prompt or add an agent**
Add `ai/prompts/<name>_v(N+1).py` (never edit a published version), point the agent at it, define/extend the output schema in `ai/schemas.py` with `_clean_text`/`_clean_list`, add a deterministic sample to `MockAIProvider` (`integrations/ai_providers/mock_provider.py`), record calls in `ai/service.py`, keep a manual path, and test with the mock (failure and invalid scenarios too). Never call the real API in tests.

**Add a real email provider (future)**
Implement `EmailProvider` (`integrations/email_providers/base.py`) with `is_simulated = False`, register it in `factory.py`. Real sending still requires `ALLOW_REAL_SUBMISSIONS=true`, a non-demo department and a non-reserved domain (`_check_real_send_allowed`). Do not bypass approval or idempotency.

**Add verified real departments**
Fill a JSON file like `docs/authorities.example.json` from an official government page, then `python -m scripts.import_authorities file.json` (checks) and `--apply` (writes). Never type contacts from memory or let AI generate them.

**Add a page / UI feature**
Client component under `features/<domain>/components/`, thin route in `src/app/`, `useHydrationSafeQuery` for reads, loading skeleton + `ErrorState` with retry + empty state, labelled regions, then a Vitest component test (mock `fetch` like `features/complaints/components/response-tracking.test.tsx`) and, for journeys, a Playwright spec using `e2e/helpers.ts`.

---

## 10. Testing rules and pitfalls

- Backend tests run against `TEST_DATABASE_URL`; each test is rolled back (savepoint mode, so service `commit()` calls are safe). Fixtures (`tests/conftest.py`): `client`, `other_client`, `db`, `storage` (tmp dir), `ai` (`MockAIProvider`; set `.scenario` / `.resolution_scenario`), `email` (`MockEmailProvider`; set `.scenario`, inspect `.sent`), `demo_directory`. Helpers: `register`, `create_complaint`, `upload_photo`, `make_image`, `csrf_headers`; journey helpers in `tests/test_submission.py` and `tests/test_monitoring.py`. Toggle settings with `monkeypatch.setattr(get_settings(), "...", value)`.
- **Never call real AI, email or geocoding in tests.**
- Run the **relevant tests before calling anything done**; if something could not be tested (e.g. a real external API), say so plainly.
- E2E: stop your own dev servers first (Playwright then starts fresh ones with rate limiting off, simulation on, mock providers). **Do not run e2e right after `npm run build`**: delete `frontend/.next` first. Tests run 2 at a time with 10 s assertions (more workers make `next dev` too slow on a laptop). Tests create `e2e-*@civicpulse.example` users in the **dev** database; clean them up afterwards and never delete the demo user or real accounts.
- Windows: the console is cp1252, so avoid printing non-ASCII from Python scripts (or set `PYTHONIOENCODING=utf-8`); Playwright can leave orphan dev servers (check ports 3000/8000).
- Vitest: jsdom lacks `ResizeObserver` (stubbed in `vitest.setup.ts`).

## 11. Definition of done (working agreement)

1. Change only what the task needs; don't rewrite working modules without a clear reason; prefer readable code over clever code; no new dependencies without a reason.
2. All product rules in §2 still hold.
3. Tests added/updated and passing: `pytest`, `ruff check . && ruff format --check .`, `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build` (then delete `.next`), and `npm run test:e2e` for UI flows.
4. Docs updated (`docs/*.md`, and `docs/progress.md` for milestone work) when behaviour or structure changes.
5. Report: what changed, files touched, tests run with results, known limitations.

## 12. Known limitations (current)

Simulated email and replies; fictional directory only; the real Claude model has not been called yet (mock only); dates in letters are UTC; the worker runs only when started; in-memory single-process rate limits; a decision on a repair check can't be undone (use Reopen); follow-up photos can't be deleted; page CSP is basic (no `script-src`). Full list: [docs/progress.md](docs/progress.md#known-limitations--open-questions).

## 13. Where to read more

[docs/architecture.md](docs/architecture.md) (decisions) · [docs/database.md](docs/database.md) (every table) · [docs/api.md](docs/api.md) (every endpoint) · [docs/workflows.md](docs/workflows.md) (status machine, agents, follow-up and resolution rules, demo journey) · [docs/design-system.md](docs/design-system.md) · [docs/development.md](docs/development.md) (setup, troubleshooting) · [docs/progress.md](docs/progress.md) (milestone history, verification results) · [docs/CivicPulse-AI-presentation.pptx](docs/CivicPulse-AI-presentation.pptx) (17-slide story-led overview with speaker notes).
