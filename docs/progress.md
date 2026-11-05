# Progress & Roadmap

_Last updated: 2026-11-05_

## Status

| Milestone | Status |
|---|---|
| 0 — Architecture & planning | ✅ Done |
| 1 — Project foundation | ✅ Done (2026-11-03) |
| 2 — Core complaint management | ✅ Done (2026-11-03) |
| 3 — AI integration | ✅ Done (2026-11-03) |
| 4 — Authority identification & submission | ✅ Done (2026-11-04) |
| 5 — Monitoring & follow-ups | ✅ Done (2026-11-04) |
| 6 — Resolution verification | ✅ Done (2026-11-05) |
| 7 — Final polish | ⏭️ Next |

## Milestone 0 — completed

- Inspected the repository: empty, not a git repo. Machine has Node 24, npm 11, Python 3.11. **PostgreSQL is not installed yet.**
- Wrote the architecture, database, API, workflows, design-system, and development docs, plus `CLAUDE.md`, `README.md`, `.env.example`, `.gitignore`.
- Decisions taken (with reasons in `docs/architecture.md` §2): Next.js rewrite proxy, server-side cookie sessions + CSRF token, sync SQLAlchemy, no LangGraph for now, deterministic department matching, mock providers first.
- Small schema additions beyond the brief, each with a reason: `user_sessions` table; structured address columns (`city`, `state`…) for matching; `is_simulated`, `idempotency_key`, `communication_type` on communications; `is_demo`, `parent_authority_id`, `service_timeline_days` on authorities; `public_reference` on complaints.

## Roadmap

Each milestone ends with: tests passing, docs updated, this file updated, and a summary.

### Milestone 1 — Project foundation ✅
- [x] `git init`; `frontend/` via `create-next-app@16.4.4` (TS strict, Tailwind v4, App Router, `src/`), shadcn/ui (Radix, Nova preset), Inter, theme tokens
- [x] Public layout (nav, footer) + full landing page
- [x] App layout: navy desktop sidebar; mobile top bar + bottom tab bar with a centred Report button
- [x] `lib/api-client.ts` (fetch wrapper, CSRF header, `ApiError`), TanStack Query provider
- [x] `backend/` with `pyproject.toml`, `core/` (config, database, security, errors, rate limit), `/health`
- [x] Alembic setup; migration for `users` + `user_sessions`
- [x] Auth: register/login/logout/me, Argon2, HttpOnly session cookie, HMAC CSRF token, rate limits
- [x] `/login`, `/register` pages; route protection (`proxy.ts` + AppShell); logout; `/dashboard` shell; `/settings` profile form
- [x] Seed script (demo user `demo@civicpulse.example` / `DemoPass123`)
- [x] Tests: 25 pytest, 30 Vitest, 8 Playwright e2e (4 scenarios × desktop + mobile)
- [x] Setup + dev scripts for Windows (`.ps1`) and macOS/Linux (`.sh`)
- PostgreSQL 17 installed locally via winget; databases `civicpulse` + `civicpulse_test` created.

**Changes from the plan, with reasons:**
- Next.js 16 calls middleware `proxy.ts`; Cache Components is on by default, so authenticated pages are client components (Server Components never read cookies).
- Rate limiting is a small in-house dependency instead of `slowapi` (fewer dependencies, easy to read).
- Vitest runs without `@vitejs/plugin-react` (Vite 8 handles JSX and tsconfig paths natively; the plugin had a peer-dependency conflict).
- `httpx2` instead of `httpx` for FastAPI's TestClient (Starlette 1.x deprecation).
- DB connections are forced to UTC so API timestamps never carry the server's local offset.
- Mobile tab bar has 3 tabs (Dashboard · Report · Complaints); Settings lives in the avatar menu.

### Milestone 2 — Core complaint management (no AI) ✅
- [x] `complaints`, `evidence`, `complaint_events` models + migration (plus a sequence for `CP-YYYY-NNNNNN` references)
- [x] Status machine (`complaints/status_machine.py`) with a test for all 100 status pairs
- [x] `StorageService` + `LocalStorage` (path-traversal safe); `get_storage` dependency
- [x] Upload validation: Pillow decode, JPEG/PNG/WebP only, ≤ 10 MB, pixel and size limits, EXIF/GPS stripped by re-encoding, SHA-256 of the stored file, duplicate detection, ≤ 5 photos
- [x] Early 413 for oversized uploads (`core/upload_limit.py`) before FastAPI parses them
- [x] Authorized evidence endpoint (`Cache-Control: private`, `nosniff`); another user's photo is a 404
- [x] Complaint create / list (search, category, status, sort, pagination) / get / update-draft / cancel / close / timeline; `GET /dashboard/summary`
- [x] Geocoding interface + `MockGeocoder` (fictional Demo City, country `XX`) + `NominatimGeocoder` (1 req/s, cache, identifying User-Agent required); `/locations/search`, `/locations/reverse`
- [x] Report wizard: step 1 (drag-drop, preview, replace, remove, progress bar), step 2 (manual title, category, severity, description, observed time), step 3 (search, Leaflet map pin, "use my location", address form, explicit confirm). Steps 4–6 shown as "soon". Draft saved after each step; URL `?draft=&step=` resumes it.
- [x] `/complaints` list (URL-based filters, pagination, empty/no-results states) and `/complaints/[id]` details (photos, description, location + map, timeline, status-based actions with confirm dialogs)
- [x] Dashboard stats, recent complaints, and recent activity from real data
- [x] Tests: **187 pytest** (status machine, uploads, ownership 404s, filters, dashboard, locations), **61 Vitest** (wizard schemas, payloads, photo checks, formatting), **14 Playwright** (manual complaint journey, cancel, mock address search, plus the Milestone 1 auth flows; desktop + mobile)
- [x] 10 MB through the Next.js proxy verified by hand: 9.28 MB and 9.98 MB photos accepted; 10.34 MB rejected with a clean 413
- **Done when:** a user can create, view, and track a manual complaint with a photo. ✔

**Changes from the plan, and problems found while testing (with fixes):**
- `complaint_events.seq` (auto-increment) was added: Windows' clock gave identical timestamps to events in one request, so timeline order needs a tie-breaker. Lists break ties with `public_reference`.
- `complaints.authority_id` exists but its foreign key is added with the `authorities` table in Milestone 4.
- Only `ORIGINAL` photos can be uploaded for now; `FOLLOWUP` photos arrive with resolution verification (Milestone 6).
- Next.js copies request bodies during rewrites and cut them off at 10 MB by default. Fixed with `experimental.proxyClientMaxBodySize: "12mb"` in `next.config.ts`.
- The early-413 middleware reads and discards the rest of a rejected upload (up to 64 MB), so proxies receive a proper response and the connection stays usable.
- **Hydration mismatch** (also the "1 Issue" badge seen in Milestone 1): cached query data appeared before React finished hydrating. Fixed with `useHydrationSafeQuery` in `src/lib/hydration.ts`.
- `usePathname()` blocked prerendering of the dynamic route; nav highlighting now streams in behind small Suspense boundaries, and AppShell reads `window.location` only when redirecting.
- Mobile bugs caught by e2e: a wide photo pushed the page out sideways (fixed with `grid-cols-1`), the drop zone could lose a file chosen before hydration (now disabled until interactive), and the mobile Search button had no accessible name.
- Login/register forms now use `method="post"`, so a submit before hydration can't put a password in the URL.
- Playwright on Windows needed backslash paths to start the backend.

### Milestone 3 — AI integration ✅
- [x] `AIProvider` interface (`integrations/ai_providers/base.py`) with `MockAIProvider` (scenarios `pothole`, `streetlight`, `garbage`, `not_civic`, `failure`, `invalid`; every result `is_mock`) and `AnthropicProvider` (official `anthropic` SDK 2.x, `beta.messages.parse(output_format=PydanticModel)`, server-side `fallbacks="default"` on refusal, effort `medium`, model `claude-opus-5-5` via `AI_MODEL`)
- [x] `ai_analyses` table: provider, model, prompt version, mock flag, status, structured result, error code, latency, token counts. Also `complaints.draft_subject` / `draft_body`.
- [x] Vision agent + prompt `vision.v1`: category + confidence, suggested title/description, conservative severity, observations, uncertainties, warnings; no location field, and the prompt forbids guessing one
- [x] Complaint Letter agent + prompt `complaint_letter.v1` (pulled forward from M4, as requested): the AI writes the wording only; the letter's **facts come from the database** via `letter_template.py`. A no-AI template is the manual fallback.
- [x] Prompt-injection defences: untrusted text is framed as data (`<facts>` with `<` escaped); outputs are enum- and length-constrained; every AI string is sanitised (links, emails, HTML, control characters removed); unknown output fields are dropped; AI never edits complaint fields on its own; an existing letter is only replaced with explicit consent
- [x] API: `POST/GET /complaints/{id}/analysis`, `POST /complaints/{id}/complaint-draft` (rate-limited 10/min); `AI_ANALYSIS_COMPLETED`, `AI_ANALYSIS_FAILED`, `COMPLAINT_DRAFT_GENERATED` events
- [x] Wizard step 2 = AI analysis: auto-runs once per photo, "Looking at your photo…" state (form stays usable), suggestions fill only empty fields ("Suggested by AI"), conflicting suggestions offered as "AI suggests: … Use suggestion", "Demo AI" badge, error banner + "Try again" + manual form
- [x] Wizard step 5 = complaint letter: auto-drafted, editable subject/body, "Write it again with AI" behind a confirm dialog, failure → "Use a basic template"
- [x] Details page: "What the AI sees" panel and the saved letter
- [x] Tests: **242 pytest** (55 new: output schemas, sanitising, mock scenarios, Claude adapter with a fake client, API success/failure/invalid output, ownership 404s, never-overwrite, injection cleanup, privacy), **74 Vitest** (13 new: suggestion rules, letter schema, step-2 component states), **14 Playwright** (journey now covers AI suggestions → edits → going back without overwrites → letter)
- **No ANTHROPIC_API_KEY was available, so only the mock provider ran end to end.** The Claude adapter is tested against a fake SDK client (request shape, structured output, refusal, truncation, SDK errors); it has not made a real API call.
- **Done when:** photo → editable AI suggestions works with the mock and (if a key exists) the real model. ✔ (mock)

**Changes from the plan:**
- Complaint letter generation moved from M4 into M3 (per the Milestone 3 brief). The letter is stored on the complaint (`draft_subject`, `draft_body`); M4 turns the approved text into the outgoing `communications` row.
- Generating a letter keeps the complaint in `DRAFT`. `PENDING_REVIEW` will be set by the M4 approval flow, so that status always means "ready to approve".
- `ai_analyses` has no `communication_id` yet; it arrives with the `communications` table (M5 reply classification).
- Location step's button is now "Continue" (to the letter step); "Save complaint" is on the letter step.

### Milestone 4 — Authority identification & submission ✅
- [x] `authorities` table: jurisdiction + level, city/state/country, supported categories (Postgres array, GIN index), official email/phone/website, **`source_url` + `verified_at` + `verification_notes`**, service timeline, parent (escalation) office, `is_demo`, `active`. A CHECK makes the **database refuse a real record without a source and a verification date**.
- [x] Fictional **Demo City** directory (7 departments, `@demo-city.example` emails, no phone numbers) seeded by `scripts/seed.py`; two departments deliberately overlap so the "please choose" path can be demonstrated
- [x] `scripts/import_authorities.py` for **verified real records** (check-only by default, `--apply` to write): https source required, verification date within a year, no reserved demo domains, unknown fields refused. Template: `docs/authorities.example.json`. **No real records were added.**
- [x] Deterministic matcher (`authorities/matcher.py`, a pure function, no AI): category + place → ranked matches with readable reasons and `EXACT` / `PARTIAL` / `NONE`. Only `EXACT` is pre-selected; uncertain results need the citizen's choice.
- [x] `communications` table (approved snapshot of recipient, subject, body, photo references; content hash; idempotency key; attempt count) with a CHECK that a simulated message can never be stored as `SENT`
- [x] `EmailProvider` interface + `MockEmailProvider` (`success` / `failure` / `flaky`; idempotent per key; never contacts anyone) via `get_email_provider`
- [x] Preview → explicit approval (`confirm: true` + SHA-256 of the previewed content; a stale preview is refused) → **idempotent send** (row lock, `SENDING` committed before the provider call, unique key, provider-level key, retry after failure, stuck-send recovery). Any later edit, letter rewrite, or department change withdraws the approval.
- [x] Real-send guard: `ALLOW_REAL_SUBMISSIONS=false` by default, and a real provider would still refuse demo departments and reserved domains
- [x] Events `AUTHORITY_SELECTED`, `COMPLAINT_APPROVED`, `APPROVAL_WITHDRAWN`, `SUBMISSION_ATTEMPTED`, `SUBMISSION_ACCEPTED`, `SUBMISSION_FAILED`; the success event says "Simulated submission… No email was sent to a real department."
- [x] Wizard step 4 (department choice with source/verification line or "Demo directory entry" badge, "Show other departments", "Continue without a department") and step 6 (simulation notice, exact message preview, approval checkbox, "Approve and send (simulated)", "Try sending again")
- [x] Details page: "Simulated submission complete" banner, department card, chronological **submission history** with a delivery badge on every message, "Review and send" action
- [x] Tests: **289 pytest** (47 new: matcher rules incl. ties, other cities/countries, inactive and escalation-only offices; directory API; routing authorization; source-backed CHECK; importer validation; preview/approval/hash; edit-after-approval; simulated send; **send twice → one message**; concurrent and stuck sends; **provider failure → retry**; flaky provider; other users get 404 everywhere; chronological history; DB refuses simulated `SENT`; real provider blocked for demo departments), **85 Vitest** (11 new: step rules, pre-selection only for certain matches, delivery labels never claim delivery), **14 Playwright** (journey now runs through department choice, approval, simulated send, history, timeline, and dashboard on desktop + mobile)
- **Done when:** a complaint can be approved and its submission simulated; the timeline shows each step. ✔

**Changes from the plan, and problems found while testing (with fixes):**
- Approval is `POST /complaints/{id}/approve` (it creates the communication from the current letter) instead of approving an existing draft communication, and there is no `PATCH /communications/{id}`: the letter is edited on the complaint, and an approved message is an unchangeable snapshot. `GET /complaints/{id}/submission-preview` was added so the citizen approves exactly what is sent.
- `PENDING_REVIEW` now means "approved, ready to send" and is labelled **"Ready to send"** in the UI. Generating a letter keeps the complaint in `DRAFT`.
- New `SUPERSEDED` delivery status for an approval that was replaced, so an older approved version can never be sent.
- The matcher scores are simpler than the M0 sketch (city 10, state 5, national 2, +1 for an email) and drop departments of other cities entirely.
- `verified_at` is a `DATE` (the day a person checked the source), not a timestamp.
- SQLAlchemy's generic `ARRAY` can't do "contains" queries; the column uses the PostgreSQL `ARRAY` type.
- The importer allows a `verified_at` one day ahead of UTC: in India (UTC+5:30) "today" is already tomorrow in UTC for part of the day.
- Mobile bug caught by e2e: a screen-reader-only "(completed)" label in the step indicator escaped its scrolling strip and made the whole page 556 px wide on a 412 px phone, which moved the send button under the tab bar. Fixed with `relative` on each step. The e2e overflow check now compares with the real screen width (mobile browsers widen `window.innerWidth` to fit overflowing content, which hid the bug).

### Milestone 5 — Response monitoring & smart follow-ups ✅
- [x] `scheduled_actions` table (unique keys, partial index for due rows) + `python -m app.workers.run_pending [--now]`: claims one action at a time with `FOR UPDATE SKIP LOCKED`, re-checks everything at run time, retries failures with back-off, gives up after `SCHEDULER_MAX_ATTEMPTS`, recovers runs stuck in `RUNNING`. **It never sends anything.**
- [x] Policy-aware deadlines (`monitoring/rules.py`): the department's listed response time when the directory has one, otherwise the default, and the page says which
- [x] Simulated department replies (dev/demo only, `ENABLE_SIMULATION`, refused in production): acknowledged, in progress, fixed, asks for information, declined, auto-reply, prompt-injection attempt, or custom text; stored as plain text with `is_simulated`
- [x] Monitoring agent (`reply_classification.v1`, `followup_letter.v1`) on the existing `AIProvider`; the mock reads replies with keyword rules and is labelled "Demo AI". Every call recorded in `ai_analyses` (now linked to the reply).
- [x] Fixed rules decide each reply's effect (acknowledged → `ACKNOWLEDGED`, in progress → `IN_PROGRESS`, fixed → `RESOLVED_PENDING_VERIFICATION`, info request → pause, declined → escalation, unrelated → nothing). AI readings are applied only when not `LOW` confidence; otherwise, or if the AI fails, **the citizen chooses** (manual path).
- [x] Reference numbers: safe format + must appear word-for-word in the reply + never our own; deterministic extraction works without AI
- [x] Follow-up drafts: facts from `followup_template.py`, wording from the AI or the template; edit → approve (content hash) → idempotent send, or dismiss. At most `FOLLOWUP_MAX_COUNT` per complaint, one open at a time, rules re-checked at approval and at sending.
- [x] Cancellation: pending checks and unsent reminders stop when the department replies, when it says the issue is resolved, and when the citizen withdraws (cancels) or closes the complaint
- [x] Escalation recommendation (once) with the department's higher offices **from the directory only** (email/phone as recorded, demo badge, "CivicPulse never contacts these offices for you"); says so when there is none
- [x] Timeline events for every step; `communications.seq` for reliable ordering
- [x] UI: *Response tracking* card (reference, reminder count, deadline and its basis, reminder card, reply-meaning card, escalation card, "fixed"/"info requested" notices), *Messages* list with simulated-reply labels, *Demo tools* card, dashboard *Needs your attention*
- [x] Tests: **402 pytest** (113 new: rules incl. every reply kind × every status, deadlines, reference extraction; and end to end: unanswered → 2 reminders → escalation, nothing before the deadline, never two drafts, approval/edit/dismiss, acknowledged, in progress, resolved, info request, rejection, auto-reply, AI failure and invalid output → citizen decides, prompt injection, failed reminder send + retry, failing scheduled action → back-off → `FAILED`, stuck run recovery, send twice → once, duplicate scheduling, stale-cancel defence, withdrawal and closing, simulation switch, authorization 404s), **100 Vitest** (15 new: deadline and label helpers; the panel in waiting, unanswered + approve-once/double-click, failed + retry, acknowledged, resolved, reply-to-review, escalation states), **16 Playwright** (new journey on desktop + mobile: skip ahead → reminder drafted → dashboard attention → approve and send → simulated acknowledgment with reference → "fixed" stops reminders)
- **Done when:** the unanswered-complaint flow runs end to end with simulated time. ✔

**Changes from the plan, with reasons:**
- One action type (`FOLLOWUP_CHECK`) instead of a separate `ESCALATION_CHECK`: when the reminder limit is reached, the check recommends escalation itself. Fewer moving parts.
- Check keys are "one per message" (`followup_check:<complaint>:after:<message>`) instead of numbered: naturally idempotent, whatever order things happen in.
- No `POST /followups/draft` or `/escalation` endpoint: the worker drafts reminders, and `GET /complaints/{id}/monitoring` returns everything the page needs. "Don't send it" (dismiss) was added so the citizen can always say no.
- Simulation endpoints are `/simulation/reply` and `/simulation/advance` (per-complaint "skip ahead", easier to demo than the CLI's `--now`).
- The notification bell moves to Milestone 7. The dashboard's *Needs your attention* list covers "what needs me now" without a new table.
- AI readings of replies are applied automatically only when the AI isn't unsure, and the citizen can always set the meaning when it isn't applied. This keeps a human in the loop without making every reply a chore.
- For "asks for more information", the citizen answers the department directly; replying from CivicPulse is not built.
- `ai_service._record_failure` no longer commits by itself, so the worker controls its own transaction.

**Problems found while testing (with fixes):**
- The demo AI reads the prompt-injection sample as "says it's resolved" (it contains that word). This is the designed worst case: the complaint waits for the citizen's verification; nothing is closed, verified or sent. The test now asserts exactly that.
- The *Demo tools* dropdown pushed past its card in the narrow side column (grid items default to their content width); fixed with `grid-cols-1` and `min-w-0`.

### Milestone 6 — Resolution verification ✅ (+ polish)
- [x] Follow-up ("after") photo upload: `POST /complaints/{id}/followup-evidence`, the same Pillow validation, size limits and EXIF/GPS stripping as original photos; at most 5; only between sending and closing; the original photo itself is refused ("same photo as before")
- [x] Resolution agent (`resolution.v1`): before + after photo → `ResolutionAssessment` (appears resolved / partly / not / can't determine, confidence, same place yes/no/unsure, changes, remaining problems, uncertainties, summary), sanitised, recorded in `ai_analyses`. Mock answers via `MOCK_AI_RESOLUTION`.
- [x] Uncertainty handling (`resolutions/rules.py`): plain warnings for a different or uncertain place, "can't tell", partial or not resolved, low confidence, or no AI at all, always with "The AI can be wrong. Only your own check decides."
- [x] Only the citizen decides: confirm (→ `VERIFIED_RESOLVED`, reminders stop; also possible for a fix found before the department replied) or dispute (only after a claimed repair → `REOPENED`), with an optional note and a required "I checked the place myself". AI failure never blocks the decision; "Try the AI again" retries.
- [x] Reopening: a dispute, or *Reopen complaint* on a verified/closed complaint (the Close dialog has promised this since M2), reopens monitoring and drafts a "not fixed" message (template, with the citizen's note) that is sent only after approval and doesn't use up the reminder limit
- [x] Audited history: `resolution_reviews` (one per photo, one pending per complaint, decisions never rewritten, `SUPERSEDED` when a newer photo replaces an undecided check, DB CHECK that a decision has a time), *Earlier checks* in the UI, timeline events
- [x] UI: *Check the repair* card (first on the page when a repair is claimed), before/after side by side (stacked on phones), "The AI thinks…" with Demo AI badge, decision form, *Earlier checks*; "Check the repair" and "Reopen complaint" in the status card
- [x] **Polish within M6:**
  - **Accessibility:** an axe-core audit of 15 pages (including every complaint state and wizard step) on desktop and phone found 64 issues: low contrast on success badges and the cancel button, the account menu's name not matching its visible text, content outside landmarks on login/register, two unlabelled sidebars, an invalid `<dl>`, a skipped heading level, and scrollable boxes that couldn't be reached by keyboard. All are fixed; the re-run reports **0 violations**.
  - **Responsive:** no page wider than the screen at 412 px (checked on all 15 pages); history thumbnails stay side by side on phones.
  - **Security:** security headers on every API response (`nosniff`, no framing, `no-referrer`, strict CSP for `/api`, `Cache-Control: no-store` except private photo caching) and on every page (`nosniff`, `X-Frame-Options: DENY`, referrer policy, permissions policy, CSP `frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`); rate limits on the new endpoints; `npm audit --omit=dev`: **0 vulnerabilities** (the `shadcn` CLI, the only source of advisories, moved to devDependencies; it's only needed when building).
  - **Performance:** measured instead of guessed: every API call behind a page answers in 10–22 ms on average through the dev proxy (dashboard 22 ms, monitoring 13 ms, checks 12 ms), so no change was needed. Photos already load lazily.
  - **Loading and error states:** each new panel has a skeleton, an error with "Try again", progress text ("Uploading… 40%", "Comparing the photos…") announced to screen readers, and inline errors.
  - **Reliable e2e:** a warm-up step compiles every page before the tests, assertions get 10 s, and the tests run 2 at a time (more made the dev server too slow).
- [x] Tests: **470 pytest** (68 new: rules incl. every decision × every status against the status machine, cautions; after-photo validation and EXIF stripping, duplicate and limit rejections, AI advice changes nothing, every uncertain mock answer warns, AI failure and invalid output → manual path → retry, confirm, "checked myself" required, disagreeing with the AI, confirming a self-found fix, dispute → reopen → message → approval → monitoring restarts with reminder 1, dispute only after a claim, reopen after verified/closed, open complaints can't be reopened, same decision twice / change of mind refused, newer photo supersedes, DB CHECK, ownership 404s everywhere; security headers), **113 Vitest** (13 new: labels, `canDispute`, the repair card's states: nothing before sending, upload prompt, HEIC rejected before upload, advice with Demo AI, decision needs choice + confirmation and is sent once, dispute disabled without a claim, AI failure + retry, uncertainty, history), **18 Playwright** (new on desktop + phone: claimed repair → after photo → AI advice → dispute with a note → "not fixed" message approved and sent → new claim → second photo → confirm → history, timeline, dashboard count, no horizontal scroll)
- **Done when:** a citizen can verify or dispute a claimed fix. ✔

**Verification results (2026-11-05):**
- `pytest` 470 passed; `ruff check` / `ruff format --check` clean; `alembic check`: no drift; the new migration downgrades and upgrades cleanly.
- Vitest 113 passed; ESLint and `tsc` clean; `npm run build` succeeds.
- Playwright: 18/18 in 4 consecutive runs with the final settings, including one right after deleting `.next`. Before switching to 2 workers, runs with 4 were flaky (1–4 timeouts per run under load; no failure pointed to an app bug).
- axe-core: 0 violations on 15 pages × 2 devices; no horizontal overflow.

**Changes from the plan, with reasons:**
- A follow-up photo has its own upload route (`/followup-evidence`) instead of a type flag on the existing one: the rules differ (when it's allowed, how many), and a draft photo route can't be misused for an after-photo or vice versa.
- `same_location_likely` is YES / NO / UNSURE instead of true/false: "unsure" is the honest answer for many photo pairs.
- An AI failure creates a check with `ai_status: FAILED` instead of returning 503, so the citizen's manual path is the same screen.
- A fix can also be confirmed before the department reports it (via "pending verification", so the status machine is unchanged).
- `checked_myself: true` is required for every decision and reopen: the AI never decides, and the record shows the citizen said they checked.
- The notification bell stays in M7 (not part of the M6 brief).

**Problems found while testing (with fixes):**
- With 4 parallel browsers, `next dev` served unminified chunks in 2–4 s each, so long journeys hit the 60 s limit and registrations their wait. A warm-up step, 10 s assertions and 2 workers fixed it; the suite is also faster (1.3–1.4 min instead of about 2 min).
- After the dispute flow arrived, "Check the repair" appears twice on a claimed-repair page (status card and notice); the e2e locator is scoped to the status card.
- Radix's Checkbox needs `ResizeObserver` inside a form; jsdom lacks it, so the Vitest setup has a small stub (browsers all have it).
- The UI's "not fixed" message would have shown as "Reminder 1"; it now has its own wording everywhere ("Message: not fixed", "Simulated: … sent").

### Showcase preparation (2026-11-05)
- README rewritten as the project's front page: the problem, the citizen journey with screenshots, architecture and lifecycle diagrams (Mermaid), the five agents and what each may not do, safety principles, the tech stack and why each piece was chosen, setup, a 5-minute demo script, test results and limitations.
- Screenshots in `docs/screenshots/` (landing, AI analysis, department, review and send, response tracking, repair check, complaint page, dashboard, phone), taken from the running app in demo mode with a fictional citizen, whose data was deleted afterwards.
- No application code changed in this step; the test results above still apply.

### Milestone 7 — Final polish
- [ ] Full settings page (notification and privacy settings), error handling review, manual keyboard and screen-reader pass (M6 did the automated a11y, responsive and security-header pass)
- [ ] Notification bell (`GET /notifications`, mark seen), moved from M5
- [ ] Playwright demo journey (`docs/workflows.md` §6)
- [ ] Docs refresh, deployment notes

## Known limitations / open questions

- **The real Claude model hasn't been called.** To try it: set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env` and restart the backend. Each analysis or letter is one API call (billed to that key). Prompts may need tuning after real-world testing.
- The mock AI ignores the photo: it always returns its scenario's sample answer (clearly labelled "Demo AI").
- AI rate limiting is per IP and in memory, like the login limit.
- Letters are English only; the prompts are ready for a `language` parameter later.
- Observation times in letters are shown in UTC (the backend doesn't know the citizen's time zone).

- **Replies are simulated only.** There is no inbound email integration; real replies would need a mail provider (e.g. Gmail API) feeding `monitoring.service.receive_reply`.
- The worker runs only when started (by hand, Task Scheduler or cron); there is no always-on scheduler process.
- The mock AI reads replies by keywords. The real Claude prompts for replies and reminders are written and schema-checked but **were not called** (no API key), like M3.
- A reply's meaning can't be changed once set (status changes can't be undone by the status machine). If the AI reads a reply wrongly with confidence, the citizen can close the complaint or dispute a claimed fix.
- Dates inside reminders are written in UTC, so a complaint sent after midnight in India shows the previous day (e.g. "03 November" for 01:36 IST on 4 November).
- The demo directory has no phone numbers (we never invent any), so escalation shows email only; phones appear only for verified records added with the importer.
- **The Resolution agent's real Claude prompt was never called** (no API key); the mock doesn't look at photos, it returns the configured `MOCK_AI_RESOLUTION` answer. Real-world accuracy of photo comparison is unknown, which is why the citizen always decides.
- A decision on a check can't be undone. If a citizen confirmed by mistake, *Reopen complaint* is the way back (recorded in the history).
- Follow-up photos can't be deleted once uploaded (they're part of the audit trail).
- The CSP for pages only sets rules that can't break Next.js (no `script-src`): a strict, nonce-based CSP needs dynamic rendering and is left for deployment.
- Accessibility was checked with axe-core (automated) only; a manual screen-reader pass is still to do.
- Withdrawing a submitted complaint doesn't tell the department; the page says so.
- **Submissions are simulated only.** No real email provider exists, `ALLOW_REAL_SUBMISSIONS` is off, and the project ships no real government contacts. The directory covers only the fictional Demo City; with a real address you'll get "No department in the directory…" and can finish the letter to send it yourself.
- The mock email provider keeps its idempotency memory in the process, so it resets on restart (the database `idempotency_key` and status checks still prevent duplicates).
- The outgoing message references the photos; a real provider would need to attach the files.
- A submitted complaint can be withdrawn (cancel) but not corrected.
- Address search uses the **mock** geocoder by default (fictional "Demo City", country `XX`; its map pins are at sea near 0°,0°). Real search needs `GEOCODER=nominatim` plus your own contact in `NOMINATIM_USER_AGENT`. **The Nominatim adapter is unit-tested against Nominatim's documented response format but was not called live** (no contact address configured; its usage policy forbids anonymous or automated use).
- Map tiles come from the public OpenStreetMap tile server: fine for development, not for heavy production traffic.
- HEIC photos (iPhone default) are rejected with a helpful message; converting them is future work.
- Uploads larger than 12 MB that bypass the browser check (e.g. sent with curl) through the Next.js dev proxy fail with a generic 500 after a 30-second timeout, instead of a 413 (verified with a 13 MB file). The UI never sends them, and the backend itself answers 413 immediately. In production, put the API behind a real reverse proxy (nginx etc.) with its own body limit.
- Deleting a complaint draft isn't offered (cancel instead). Abandoned drafts stay in the database.
- Notification and privacy settings are shown as "later milestone" cards; the DB columns already exist.
- Registration reveals whether an email is already registered (409). Acceptable for the MVP; rate limiting reduces abuse.
- In-memory rate limiting only works for a single backend process, and resets on restart.
- The e2e tests write `e2e-*@civicpulse.example` users into the development database (cleanup command in `docs/development.md` §6).
- `npm audit --omit=dev` is clean. The full `npm audit` still lists 6 low/moderate advisories in the `shadcn` CLI (`deepmerge`, `minimatch` via `ts-morph`), a development-only code generator that the app and build don't execute; the fix is a breaking downgrade, so it's left as is.
- The authority directory has **fictional demo records** only. Real records need manual verification and the importer (`docs/database.md` §4); nobody has verified any yet.
- The Gmail API integration and S3 storage are planned but not part of the MVP milestones.
