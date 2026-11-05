# API

> Status: **Milestones 1–6 implemented** (✅ below): health, auth, profile, complaints, evidence, dashboard, locations, AI, authorities, submission, replies, follow-ups, resolution verification. The rest is the plan. Live, always-accurate docs: `http://localhost:8000/docs`.

All routes live under **`/api/v1`**. Requests and responses are JSON unless noted.

## Conventions

- **Auth:** the `cp_session` HttpOnly cookie. Every route except `/health`, `/auth/register`, and `/auth/login` requires it.
- **CSRF:** unsafe methods (POST/PUT/PATCH/DELETE) must send `X-CSRF-Token` equal to the `cp_csrf` cookie.
- **Ownership:** asking for another user's complaint returns **404**, not 403, so IDs can't be probed.
- **Errors** always have one shape:
  ```json
  { "error": { "code": "INVALID_STATUS_TRANSITION", "message": "A cancelled complaint cannot be submitted.", "details": {} } }
  ```
  Codes: `VALIDATION_ERROR` (422), `UNAUTHENTICATED` (401), `CSRF_FAILED` (403), `NOT_FOUND` (404), `CONFLICT` (409), `INVALID_STATUS_TRANSITION` (409), `FILE_REJECTED` (400/413), `RATE_LIMITED` (429), `AI_UNAVAILABLE` (503), `SUBMISSION_FAILED` (503), `REAL_SUBMISSION_BLOCKED` (403), `INTERNAL_ERROR` (500).
- **Pagination:** `?page=1&page_size=10` → `{ "items": [...], "page": 1, "page_size": 10, "total": 42 }`.
- **Rate limits** (per IP or user): login/register 10/min, uploads 20/min, AI endpoints (incl. photo comparison) 10/min, approve/send 10/min, resolution decisions and reopening 10/min, simulation 30/min.
- **Security headers** (M6) on every API response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, and `Cache-Control: no-store` unless a route sets its own (photos: `private, max-age=3600`).

## Endpoints by milestone

### Health — M1
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | ✅ `{ "status": "ok" \| "degraded", "database": "ok" \| "error" }` (provider fields added when providers exist) |

### Authentication — M1 ✅
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | `{name, email, password}` → `201 {user}`, starts a session (sets cookies). `409` if the email exists. Password: 8–128 chars with a letter and a number. |
| POST | `/auth/login` | `{email, password}` → `200 {user}`, sets `cp_session` (HttpOnly) + `cp_csrf` cookies. `401 "Incorrect email or password."` for any failure. |
| POST | `/auth/logout` | `204`. Revokes the session row and clears both cookies. Needs CSRF. |
| GET | `/auth/me` | `200 {user}` or `401`. Also re-issues the cookies. |

`user` = `{ id, name, email, created_at }`. Emails are normalised to lower case; names are trimmed.

### Users / Settings — M1 (profile) ✅, M7 (rest)
| Method | Path | Purpose |
|---|---|---|
| PATCH | `/users/me` | ✅ `{name}` → updated user. Notification and privacy settings are added in M7. |
| POST | `/users/me/password` | M7: change password (requires current password) |

### Complaints — M2 ✅
| Method | Path | Purpose |
|---|---|---|
| POST | `/complaints` | `201` new **DRAFT**. Body optional (any editable field, see PATCH). Gets a `public_reference` like `CP-2026-000123`. |
| GET | `/complaints` | own complaints, `Page<ComplaintListItem>`. Query: `search` (title, description, reference, address, locality, city; case-insensitive; `%` and `_` are literal), `category`, `status`, `sort` = `-created_at` (default) \| `created_at` \| `-updated_at`, `page` (≥ 1), `page_size` (1–50, default 10). |
| GET | `/complaints/{id}` | `ComplaintRead`: all fields, `evidence[]` (each with a `url`), and `available_actions` (`edit`, `add_photo`, `submit`, `verify`, `reopen`, `cancel`, `close`) that the UI turns into buttons, and `authority` (the selected department or `null`). |
| PATCH | `/complaints/{id}` | Send only changed fields: `title` (5–160), `description` (≤ 5000), `category`, `severity`, `address_line`, `locality`, `city`, `state`, `postal_code`, `country` (ISO-2), `latitude` + `longitude` (together), `observed_at` (with time zone, not in the future), `confirm_location: true` (needs address + city). Only in `DRAFT`/`PENDING_REVIEW`, otherwise `409`. Editing the location clears an earlier confirmation. Any change to an approved complaint withdraws the approval (`PENDING_REVIEW → DRAFT`); changing the category clears a department that doesn't handle the new one. |
| POST | `/complaints/{id}/cancel` | → `CANCELLED` (`409 INVALID_STATUS_TRANSITION` if not allowed). For a submitted complaint this is the citizen **withdrawing** it: pending checks and unsent reminders are cancelled (M5); the department is not notified automatically. |
| POST | `/complaints/{id}/close` | → `CLOSED` (only from `SUBMITTED` and later statuses). Stops reminders (M5). |
| GET | `/complaints/{id}/timeline` | events, oldest first: `{event_type, previous_status, new_status, description, actor, created_at}` |
| GET | `/dashboard/summary` | `{stats: {total, drafts, active, pending_responses, verified_resolutions}, recent_complaints (5), recent_activity (8), needs_attention (≤ 10)}`. `needs_attention` (M5): one item per complaint, most urgent first: `{complaint_id, complaint_reference, complaint_title, kind, message}`, `kind` = `VERIFY_FIX`, `FOLLOWUP_FAILED`, `FOLLOWUP_READY`, `REPLY_TO_REVIEW`, `INFO_REQUESTED`, `ESCALATION`. `total` excludes cancelled; `active` = submitted and not finished; `pending_responses` = `SUBMITTED`. |

### Evidence — M2 ✅
| Method | Path | Purpose |
|---|---|---|
| POST | `/complaints/{id}/evidence` | Multipart field `file`. Real JPEG/PNG/WebP only (decoded by Pillow; filename and declared type are ignored), ≤ 10 MB (`413`), 64 px – 40 MP, max 5 photos, no duplicates (`409`). EXIF/GPS metadata is stripped. Only while the complaint is editable. |
| POST | `/complaints/{id}/followup-evidence` | ✅ M6: an "after" photo to check a repair. Same validation, EXIF stripping and size limits; `FOLLOWUP` type; at most 5. Only after the complaint was sent and until it is closed (`SUBMITTED` … `RESOLVED_PENDING_VERIFICATION`, `REOPENED`), otherwise `409`. The same photo as the original is refused (`409`: "This is the same photo as before"). |
| GET | `/evidence/{evidence_id}/file` | The cleaned image, owner only. Headers: `Cache-Control: private, max-age=3600`, `X-Content-Type-Options: nosniff`. |
| DELETE | `/evidence/{evidence_id}` | `204`. Removes a photo while the complaint is editable. |

### Locations — M2 ✅
Both need a login and are rate-limited (30/min). The UI only searches when the user presses Search, never as autocomplete.

| Method | Path | Purpose |
|---|---|---|
| GET | `/locations/search?q=` | `{provider: "mock" \| "nominatim", results: LocationResult[]}`; `q` is 3–200 chars. `503` if the provider can't be reached. |
| GET | `/locations/reverse?lat=&lon=` | `{provider, result: LocationResult \| null}` |

`LocationResult` = `{label, address_line, locality, city, state, postal_code, country, latitude, longitude}`.

### AI — M3 ✅
Rate-limited (10/min). Only while the complaint is editable. A provider failure or invalid model output gives `503 AI_UNAVAILABLE` with `details.reason` (`PROVIDER_ERROR`, `TIMEOUT`, `RATE_LIMITED`, `REFUSED`, `INVALID_OUTPUT`) and a message pointing to the manual path. The failure is still recorded in `ai_analyses`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/complaints/{id}/analysis` | `{evidence_id?}` (default: first photo) → `201 AnalysisRead`: `{id, status, provider, model, prompt_version, is_mock, evidence_id, result: VisionAnalysis, error_code, created_at}`. `VisionAnalysis` = `{is_civic_issue, category, category_confidence, suggested_title, suggested_description, severity, observations[], uncertainties[], warnings[]}`. **Never changes the complaint.** `422` without a photo. |
| GET | `/complaints/{id}/analysis` | latest successful analysis, or `null` |
| POST | `/complaints/{id}/complaint-draft` | `{mode: "ai" \| "template", replace_existing: false}` → `{draft_subject, draft_body, source, is_mock, analysis_id}`, also saved on the complaint. Needs title, description, category, and a confirmed location (`422` lists what's missing). An existing letter gives `409` unless `replace_existing` is true. `mode: "template"` uses no AI. |

The citizen edits the letter with `PATCH /complaints/{id}` and `draft_subject` (5–200 chars) / `draft_body` (20–10,000).

### Authorities — M4 ✅
All need a login. The directory is read-only through the API; records come from the seed script (fictional demo city) or the verified-record importer.

| Method | Path | Purpose |
|---|---|---|
| GET | `/authorities` | active departments, `AuthorityRead[]`. Query: `q` (name or jurisdiction), `category`, `city`. |
| GET | `/authorities/{id}` | one department: contacts, `source_url`, `verified_at`, `verification_notes`, `is_demo` |
| GET | `/complaints/{id}/authority-matches` | `{confidence, matches: [{authority, score, reasons[]}], selected_authority_id}`. `confidence` is `EXACT` (one clear city department), `PARTIAL` (a tie, or only state/national matches: the citizen must choose), or `NONE`. `422` without a category or city. |
| PUT | `/complaints/{id}/authority` | `{authority_id}` → `ComplaintRead`. Only while editable. `404` for an unknown or inactive department; `422` if it doesn't handle the complaint's category or has no email. Withdraws an earlier approval. |

`AuthorityRead` = `{id, name, jurisdiction, jurisdiction_level, city, state, country, supported_categories[], official_email, official_phone, website_url, source_url, verified_at, verification_notes, service_timeline_days, parent_authority_id, is_demo}`.

### Submission & communications — M4 ✅ (outbound), M5 (inbound)
Approve and send are rate-limited (10/min). Error codes added in M4: `SUBMISSION_FAILED` (503, the provider failed; nothing was delivered; retry allowed) and `REAL_SUBMISSION_BLOCKED` (403, the real-send safety guard).

| Method | Path | Purpose |
|---|---|---|
| GET | `/complaints/{id}/submission-preview` | exactly what would be sent: `{ready, missing[], authority, recipient, from_address, subject, body, attachments[], is_simulated, content_sha256, pending_communication}`. `missing` lists what's still needed (photo, title, description, type, confirmed location, a department with an email, a letter). |
| POST | `/complaints/{id}/approve` | `{confirm: true, content_sha256}` → `201 CommunicationRead` (`APPROVED`). `409` if the hash doesn't match the current content (something changed since the preview), `422` if anything is missing. Moves the complaint `DRAFT → PENDING_REVIEW`. Approving the same content again returns the same message. |
| POST | `/communications/{id}/send` | sends the approved snapshot. **Idempotent:** a sent message is returned as is, never sent twice. `409` if the approval was superseded, the content changed, or another send is in progress. On provider failure: `503 SUBMISSION_FAILED`, message `FAILED`, and the same call can be retried. On success the complaint becomes `SUBMITTED`. |
| GET | `/complaints/{id}/communications` | the submission history, oldest first |

`CommunicationRead` = `{id, direction, communication_type, channel, recipient, sender, subject, body, attachments[], delivery_status, is_simulated, provider, attempt_count, error_message, sent_at, received_at, created_at, followup_number, reply_kind, reply_kind_source, reply_summary, reference_number}`. `delivery_status` is `DRAFT` (reminders), `APPROVED`, `SENDING`, `SENT`, `SIMULATED_SENT`, `FAILED`, `SUPERSEDED`, `CANCELLED` (a reminder not sent), or `RECEIVED` (replies). **`is_simulated` is always shown in the UI**, and the database refuses `SENT` for a simulated message.

### Replies, follow-ups & escalation — M5 ✅
The worker (`python -m app.workers.run_pending`) **only drafts** reminders. Each one is approved and sent by the citizen with the same content-hash approval and idempotent send as the complaint. Nobody is ever contacted automatically.

| Method | Path | Purpose |
|---|---|---|
| GET | `/complaints/{id}/monitoring` | `{monitored, response_due_at, deadline_basis, deadline_official, followups_sent, followups_max, authority_reference_number, open_followup, open_followup_sha256, replies_to_review[], latest_reply, escalation}`. `escalation` = `{recommended_at, reason, contacts: AuthorityRead[]}` (directory records only), or `null`. |
| PATCH | `/communications/{id}` | edit a reminder: `{subject?, body?}` (5–200 / 20–10,000 chars). Only `DRAFT`, `APPROVED` or `FAILED` reminders; an approved one goes back to `DRAFT` and must be approved again. |
| POST | `/communications/{id}/approve` | `{confirm: true, content_sha256}` (= `open_followup_sha256`) → `APPROVED`. `409` if the text changed, the limit was reached, or the complaint is no longer waiting. Repeating it is harmless. |
| POST | `/communications/{id}/send` | the same idempotent send as in M4. For a reminder: anti-spam rules checked again; on success `FOLLOWUP_SENT` and the next check is scheduled. |
| POST | `/communications/{id}/dismiss` | the citizen doesn't send the reminder → `CANCELLED`; a new check is scheduled one interval later |
| PUT | `/communications/{id}/reply-kind` | `{kind}`: the citizen says what a reply means (manual path when the AI was unavailable or unsure). `409` if it already has a meaning. Same rules as an AI reading. |

`kind` (reply meaning) = `ACKNOWLEDGMENT`, `IN_PROGRESS`, `RESOLVED_CLAIM`, `REQUEST_FOR_INFO`, `REJECTION`, `UNRELATED`.

#### Simulation (development / demo only)
Only with `ENABLE_SIMULATION=true` (the backend refuses to start with it in production). Otherwise these return `404`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/simulation` | `{enabled, reply_scenarios: [{id, label}]}` (always available; `enabled: false` hides the demo tools) |
| POST | `/complaints/{id}/simulation/reply` | `{scenario}` (`acknowledged`, `in_progress`, `resolved`, `need_info`, `rejected`, `auto_reply`, `injection`) **or** `{body}` (5–5000 chars) → `201` simulated inbound reply (`is_simulated: true`), then the Monitoring agent and the rules run. `409` before the complaint was sent. |
| POST | `/complaints/{id}/simulation/advance` | "skip ahead": runs this complaint's next scheduled check as if its date had arrived → `{ran: [ScheduledActionRead]}`. `409` if nothing is scheduled. |

### Resolution verification — M6 ✅
The AI comparison is **advice only**. Only the citizen's decision changes the status, and the citizen must confirm they checked the place themselves.

| Method | Path | Purpose |
|---|---|---|
| POST | `/complaints/{id}/resolution-reviews` | `{evidence_id}` (a `FOLLOWUP` photo) → `201 ResolutionReviewRead`: the **Resolution agent** compares it with the original photo. An AI failure is not an error: `ai_status: "FAILED"` and the citizen compares the photos. The same photo again returns the same check (and retries the AI if it failed). A new photo replaces an undecided older check (`SUPERSEDED`). `422` for an original photo, `404` for another complaint's photo. |
| GET | `/complaints/{id}/resolution-reviews` | the history of checks, oldest first (never deleted) |
| POST | `/resolution-reviews/{id}/decision` | `{decision: CONFIRMED_RESOLVED \| DISPUTED, notes? (≤ 1000), checked_myself: true}`. Confirm: from `RESOLVED_PENDING_VERIFICATION` → `VERIFIED_RESOLVED`; from a waiting status (`SUBMITTED`/`ACKNOWLEDGED`/`IN_PROGRESS`/`REOPENED`) via `RESOLVED_PENDING_VERIFICATION`; reminders stop. Dispute: only after the department claimed a repair → `REOPENED`, plus a **"not fixed" message draft** for the citizen to approve. The same decision twice is harmless; a different one is `409`. |
| POST | `/complaints/{id}/reopen` | `{notes?, checked_myself: true}`: the problem came back after `VERIFIED_RESOLVED` or `CLOSED` → `REOPENED`, plus a "not fixed" message draft. `409` otherwise. |

`ResolutionReviewRead` = `{id, complaint_id, followup_evidence, original_evidence, ai_status, ai_error_code, is_mock, assessment, cautions[], decision (PENDING | CONFIRMED_RESOLVED | DISPUTED | SUPERSEDED), citizen_notes, decided_at, created_at}`. `assessment` = `{assessment: APPEARS_RESOLVED | PARTIALLY_RESOLVED | NOT_RESOLVED | CANNOT_DETERMINE, confidence, same_location_likely: YES | NO | UNSURE, visible_changes[], remaining_problems[], uncertainties[], summary}`. `cautions` are plain-language warnings from `resolutions/rules.py` (different place, unsure, low confidence, AI unavailable…), always ending with "The AI can be wrong. Only your own check decides."

The "not fixed" message is a `FOLLOW_UP` communication with `followup_number: null`: approved and sent like a reminder (`/communications/{id}/approve`, `/send`, `/dismiss`), but it doesn't count towards `FOLLOWUP_MAX_COUNT`.

### Notifications — M7
In M5 the dashboard's `needs_attention` list covers "what needs me now". A notification bell (`GET /notifications`, `POST /notifications/mark-seen`) is planned with the M7 polish.

## Mapping to the original spec's API list

| Spec item | Endpoint |
|---|---|
| Update draft | `PATCH /complaints/{id}` |
| Approve complaint / Approve submission | `POST /complaints/{id}/approve` (creates the `COMPLAINT` communication) |
| Submit complaint | `POST /communications/{id}/send` |
| Preview message | `GET /complaints/{id}/submission-preview` |
| Submission history | `GET /complaints/{id}/communications` |
| Generate complaint | `POST /complaints/{id}/complaint-draft` |
| Verify resolution | `POST /complaints/{id}/followup-evidence` → `POST /complaints/{id}/resolution-reviews` → `POST /resolution-reviews/{id}/decision` |
| Get matching department | `GET /complaints/{id}/authority-matches` |
| Process simulated replies | `POST /complaints/{id}/simulation/reply` |
| Generate / approve reminder | drafted by the worker; `POST /communications/{id}/approve` + `/send` |
