# Architecture

> Status: **Milestones 1–6 implemented** (foundation, auth, complaints, photos, locations, AI, departments, submission, monitoring and follow-ups, resolution verification). The notification bell is planned for M7.

## 1. Big picture

CivicPulse AI is a **modular monolith**: one FastAPI backend process, one Next.js frontend, one PostgreSQL database, and one separately-run Python worker command.

```
 Browser
   │  (same origin: http://localhost:3000)
   ▼
┌──────────────────────────┐        /api/v1/*  (rewrite/proxy)       ┌──────────────────────────────┐
│  Next.js frontend        │ ──────────────────────────────────────▶ │  FastAPI backend (:8000)     │
│  - pages & UI            │                                         │  routers → services → models │
│  - TanStack Query cache  │ ◀────────────────────────────────────── │  - auth / authorization      │
│  - no secrets            │            JSON / image bytes           │  - AI agents                 │
└──────────────────────────┘                                         │  - status rules              │
                                                                     └──────┬──────────┬────────────┘
                                                                            │          │
                                                        SQLAlchemy          │          │ provider interfaces
                                                                            ▼          ▼
                                                                   ┌────────────┐  ┌─────────────────────────┐
                                                                   │ PostgreSQL │  │ Integrations            │
                                                                   │ (local or  │  │ - AI: mock | Anthropic  │
                                                                   │  Supabase) │  │ - Email: mock | Gmail*  │
                                                                   └─────▲──────┘  │ - Storage: local | S3*  │
                                                                         │         │ - Geocoding: mock | OSM │
                                                     ┌───────────────────┴──┐      └─────────────────────────┘
                                                     │ Worker command       │       * = later milestones
                                                     │ python -m            │
                                                     │ app.workers.run_     │
                                                     │ pending              │
                                                     └──────────────────────┘
```

### Why a modular monolith?

- **One deployable backend** is far easier to run, debug, and demo than microservices.
- **Modules with clear boundaries** (auth, complaints, evidence…) keep the code organised so any one of them could be extracted later if there were ever a real reason.
- Students can trace a request from the router to the service to the database in a single codebase.

## 2. Key architectural decisions

| Decision | Choice | Reason |
|---|---|---|
| Frontend ↔ backend connection | Next.js **rewrites** `/api/v1/*` to the FastAPI server | Browser sees one origin → cookies just work, almost no CORS pain, and the backend URL never appears in client code. |
| Authentication | **Server-side sessions**: random token in an `HttpOnly`, `SameSite=Lax` cookie; only a SHA-256 hash stored in `user_sessions` | Real logout and revocation, no JWT pitfalls, nothing secret readable by JavaScript. |
| CSRF | Double-submit token: readable `csrf_token` cookie, echoed in an `X-CSRF-Token` header on POST/PUT/PATCH/DELETE | Cheap and standard defence on top of `SameSite=Lax`. |
| Password hashing | Argon2 via `pwdlib` | Current recommended algorithm; used in FastAPI's own docs. |
| Database access | **Sync** SQLAlchemy 2.x + `psycopg` 3 | Simpler to read and test than async. FastAPI runs sync endpoints in a thread pool, which is plenty for this workload. Every connection is set to UTC, so the API always returns UTC timestamps. |
| Rate limiting | A ~40-line in-memory limiter (`core/rate_limit.py`) used as a route dependency | Easy to read, no extra dependency. Single-process only; swap in a shared store if the backend ever runs as several processes. |
| Rendering strategy | Next.js 16 with Cache Components. Authenticated pages are **client components** that load data with TanStack Query. | Server Components never read the session cookie, so every page prerenders as a static shell and auth logic lives in one place (the API). |
| Hydration safety | Query hooks are wrapped in `useHydrationSafeQuery` (`src/lib/hydration.ts`) | The prerendered HTML has no user data. Until React finishes hydrating, queries report "loading" like the server did; otherwise cached data causes hydration mismatches. |
| URL-dependent client hooks | `useSearchParams`, `useParams`, `usePathname` only inside `<Suspense>` | With Cache Components, these suspend during prerendering. The nav links' active highlight streams in behind small boundaries. |
| Upload size limits | Browser check → Next.js `proxyClientMaxBodySize: "12mb"` → backend `UploadSizeLimitMiddleware` (Content-Length) → route reads at most limit + 1 byte | Each layer stops oversized files as early as possible without truncating legal 10 MB photos. |
| Photo privacy | Every upload is decoded and re-encoded with Pillow | Removes EXIF/GPS/device metadata, normalises orientation, and guarantees the stored file is a real image. |
| Migrations | Alembic, autogenerate then reviewed by hand | Schema history lives in git. |
| Enums in the DB | `VARCHAR` columns + Python `StrEnum` validation (+ `CHECK` constraint on `status`) | Adding a category doesn't need a painful Postgres `ALTER TYPE`. |
| AI orchestration | Plain Python "agent" classes called by services. **No LangGraph yet.** | The workflow is user-driven, with a human approval gate between every step, so it needs no autonomous graph. LangGraph gets reconsidered only if a real multi-step autonomous loop appears. |
| AI provider | `AIProvider` interface with `MockAIProvider` and `AnthropicProvider` | Works with no API key; the real model is swapped in through one env var. |
| Background work | `scheduled_actions` table + `python -m app.workers.run_pending` | Survives restarts and can run by hand in a demo or from cron / Task Scheduler. No in-process timers. |
| Files | `StorageService` interface; `LocalStorage` writes to `backend/storage/` (outside any public folder) | Swapping in S3 means a new class, with no changes to callers. |
| Department lookup | **Deterministic** matching against a curated `authorities` table | The AI never invents department names, emails, or phone numbers. |
| Email | `EmailProvider` interface; `MockEmailProvider` first, Gmail API later | Simulated sends are always labelled as simulated. |
| Maps / geocoding | Leaflet + OpenStreetMap tiles; geocoding through a backend proxy (`mock` or `nominatim`) | Free, no API key. The backend proxy respects Nominatim's usage policy (rate limit, User-Agent) and keeps the frontend simple. |

## 3. Backend layering

Every backend module follows the same small pattern:

```
modules/complaints/
├── router.py      # HTTP only: parse request, call service, return schema. No business rules.
├── service.py     # Business logic: permission checks, status rules, orchestration.
├── models.py      # SQLAlchemy ORM tables.
├── schemas.py     # Pydantic request/response models (the API contract).
├── constants.py   # Enums: ComplaintStatus, Category, Severity…
└── (optional) status_machine.py, repository helpers, etc.
```

**Rules**

1. Routers never touch the database directly; they call services.
2. Services receive a `Session` and the current user. They raise domain errors (`NotFoundError`, `PermissionDeniedError`, `InvalidTransitionError`…) that one global handler converts to consistent JSON errors.
3. Cross-module calls go through the other module's **service**, never its models directly. The exception is reading foreign keys.
4. Integrations (AI, email, storage, geocoding) are only reached through their interface, obtained from a small factory driven by settings.

### Backend folder layout

```
backend/
├── app/
│   ├── main.py                    # create FastAPI app: CORS, global CSRF check, error handlers
│   ├── api_router.py              # registers every module router under /api/v1 (+ /health)
│   ├── models.py                  # imports every ORM model so Alembic can see them
│   ├── core/
│   │   ├── config.py              # pydantic-settings Settings (reads the repo-root .env)
│   │   ├── database.py            # engine (UTC), SessionLocal, Base, get_db / DbSession
│   │   ├── security.py            # Argon2 password hashing, session tokens, CSRF tokens
│   │   ├── errors.py              # domain exceptions + one JSON error shape
│   │   ├── rate_limit.py          # small in-memory RateLimit dependency
│   │   ├── upload_limit.py        # middleware: early 413 for oversized uploads
│   │   └── security_headers.py    # ✅ middleware: nosniff, no framing, no-store, strict CSP for /api
│   ├── modules/
│   │   ├── auth/                  # router, service, models (user_sessions), schemas,
│   │   │                          # cookies.py (set/clear), dependencies.py (CurrentUser, verify_csrf)
│   │   ├── users/                 # profile; users table (preferences/privacy columns ready)
│   │   ├── complaints/            # ✅ constants, status_machine, models (complaints + events),
│   │   │                          #    schemas, service (incl. dashboard), router
│   │   ├── evidence/              # ✅ image_validation (Pillow), models, service, router
│   │   ├── locations/             # ✅ /locations/search + /reverse (geocoding through the backend)
│   │   ├── authorities/           # ✅ models, matcher (pure function), demo_data, schemas
│   │   │                          #    (incl. AuthorityImport validation), service, router
│   │   ├── ai/                    # ✅ agents/ (vision, complaint_writer), prompts/ (versioned),
│   │   │                          #    schemas (AI outputs), sanitize, letter_template, image_prep,
│   │   │                          #    models (ai_analyses), service, router
│   │   ├── communications/        # ✅ models, schemas, service (preview, content hash, approve,
│   │   │                          #    idempotent send for complaints AND reminders, reminder
│   │   │                          #    edit/approve/dismiss, history), hashing, router
│   │   ├── monitoring/            # ✅ rules (pure: deadlines, reply effects, reference numbers,
│   │   │                          #    anti-spam), models (scheduled_actions), service (replies,
│   │   │                          #    worker, reminders, escalation, attention), simulation, router
│   │   ├── resolutions/           # ✅ models (resolution_reviews), rules (pure: cautions, allowed
│   │   │                          #    decisions), schemas, service (compare, decide, reopen), router
│   │   └── notifications/         # (M7) bell; M5's dashboard "Needs your attention" covers it
│   ├── integrations/
│   │   ├── ai_providers/          # ✅ base.py (AIProvider), mock_provider.py, anthropic_provider.py, factory.py
│   │   ├── email_providers/       # ✅ base.py (EmailProvider), mock_provider.py, factory.py (gmail later)
│   │   ├── storage/               # ✅ base.py (StorageService), local_storage.py, factory.py
│   │   └── geocoding/             # ✅ base.py (Geocoder), mock_geocoder.py, nominatim_geocoder.py, factory.py
│   ├── workers/
│   │   └── run_pending.py         # ✅ runs due scheduled_actions once, then exits (--now for demos)
│   └── common/
│       ├── time.py                # utc_now() (overridable in tests / demo time-travel)
│       ├── pagination.py
│       └── text.py                # sanitising untrusted text (emails, AI output)
├── alembic/                       # env.py + versions/ (one file per migration)
├── scripts/seed.py                # demo user + fictional Demo City directory
├── scripts/import_authorities.py  # checks / imports VERIFIED real departments (JSON file)
├── tests/                         # pytest; conftest.py migrates the test DB, rolls back per test
├── storage/                       # local uploaded files (git-ignored)
└── pyproject.toml
```

## 4. Frontend layering

```
frontend/src/
├── app/                           # Next.js App Router routes only (thin)
│   ├── (marketing)/page.tsx       # /             public layout with top nav + footer
│   ├── (auth)/login/page.tsx      # /login
│   ├── (auth)/register/page.tsx   # /register
│   └── (app)/                     # authenticated layout with sidebar
│       ├── dashboard/page.tsx
│       ├── report/page.tsx
│       ├── complaints/page.tsx
│       ├── complaints/[id]/page.tsx
│       └── settings/page.tsx
├── components/
│   ├── ui/                        # shadcn/ui primitives (Button, Card, Input, Sheet, DropdownMenu…)
│   ├── layout/                    # Logo, PublicHeader/Footer, AppShell, AppSidebar, mobile nav,
│   │                              # UserMenu, PageHeader, nav-config.ts
│   ├── marketing/                 # landing-page sections (hero, how it works, features, CTA)
│   ├── dashboard/                 # StatCard, ActivityFeed
│   ├── complaints/                # StatusBadge, CategoryLabel, ComplaintCard, ComplaintTimeline,
│   │                              # EvidenceImage, LocationMap (+ location-map-loader: client-only)
│   └── shared/                    # EmptyState, ErrorState, FormField, FormAlert, PasswordInput,
│                                  # ImageDropzone, ConfirmDialog
├── features/                      # data + feature logic, grouped by domain
│   ├── authentication/            # api.ts, hooks.ts, schemas.ts, components/ (login + register forms)
│   ├── account/                   # profile update + settings view
│   ├── dashboard/                 # dashboard overview
│   ├── complaints/                # api.ts, hooks.ts, schemas.ts, constants.ts (labels/icons/colours),
│   │                              # submission.ts (step rules, delivery labels), components/
│   │                              # (list + detail views), report-wizard/ (steps 1–6; department
│   │                              # and review-and-send steps call authoritiesApi / submissionApi)
│   │                              # monitoring.ts (reply meanings, deadline text), components/
│   │                              # response-tracking.tsx, demo-tools.tsx (M5)
│   └── notifications/             # (M7)
├── lib/                           # api-client.ts (fetch + CSRF + ApiError + uploadFile with progress),
│                                  # query-client.ts, hydration.ts, format.ts, safe-redirect.ts, utils.ts
├── types/                         # TS types mirroring backend schemas
└── proxy.ts                       # optimistic redirect to /login for app pages (Next 16 "proxy")
```

**Rule of thumb:** `components/` holds presentational pieces that receive props. `features/` knows about the API and the business flows. Route files in `app/` stay thin: they compose feature components.

**Route protection has three layers:**
1. `src/proxy.ts` (Next.js 16's name for middleware) redirects to `/login?next=…` when there is **no** session cookie at all.
2. `AppShell` calls `GET /auth/me`. A `401` (expired or revoked session) also redirects to `/login`.
3. **The backend checks authentication (and later ownership) on every API request.** This is the only layer that actually provides security; the first two are UX.

## 5. How a request flows (example: upload evidence)

1. The browser sends `POST /api/v1/complaints/{id}/evidence` (multipart) to `localhost:3000`. Next.js forwards it to `localhost:8000`.
2. `evidence/router.py` gets the current user (session cookie) and checks the CSRF header.
3. `evidence/service.py`:
   - loads the complaint and checks that `complaint.user_id == current_user.id` (otherwise **404**, so other users' IDs aren't revealed),
   - checks the complaint status allows new evidence,
   - validates the file (size limit, real image via Pillow, allowed type),
   - re-encodes the image to strip EXIF metadata (privacy: GPS, device info),
   - computes a SHA-256 checksum and saves the file through `StorageService`,
   - inserts an `evidence` row and an `EVIDENCE_UPLOADED` complaint event in **one transaction**.
4. The router returns an `EvidenceRead` schema; TanStack Query invalidates the complaint cache.

## 6. Configuration

All configuration comes from environment variables, loaded by `core/config.py` from the **repository-root `.env`** (see `.env.example`). The frontend only needs `BACKEND_URL`, and that has a sensible default. No secret is ever read by frontend code.

## 7. Extensibility points

| Want to add… | Where |
|---|---|
| A new issue category | `complaints/constants.py` enum + label/icon map in `frontend/src/components/complaints/category-meta.ts` + authority `supported_categories` |
| A new city / department | Insert verified rows into `authorities` (see `docs/database.md` → *Adding verified authorities*) |
| A new AI provider | New class in `integrations/ai_providers/` implementing `AIProvider` + register it in `factory.py` |
| A real email channel | New `EmailProvider` (e.g. Gmail API via OAuth, `is_simulated = False`) + register it in `email_providers/factory.py`. Real sends also need `ALLOW_REAL_SUBMISSIONS=true` and verified, non-demo departments. |
| Cloud storage | New `StorageService` (S3-compatible) + `STORAGE_BACKEND=s3` |
| A mobile app | Reuse the same `/api/v1` REST API. A token-based auth option can be added beside cookie sessions. |
| Multilingual complaints | `language` parameter already planned on the Complaint Generation agent |
