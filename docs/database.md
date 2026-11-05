# Database

> Status: `users`, `user_sessions` (M1), `complaints`, `complaint_events`, `evidence` (M2), `ai_analyses` (M3), `authorities`, `communications` (M4), `scheduled_actions` (M5) and `resolution_reviews` (M6) **exist**: every table in this document.

PostgreSQL 16+ (local install or Supabase). All IDs are **UUIDs** generated in Python (`uuid.uuid4`). All timestamps are `TIMESTAMPTZ` stored in UTC.

## 1. Entity relationship overview

```
users ─┬─< user_sessions
       │
       └─< complaints >── authorities ──(parent_authority_id)──▶ authorities
              │
              ├─< evidence
              ├─< ai_analyses        (optionally → evidence, → communications)
              ├─< communications
              ├─< complaint_events
              ├─< scheduled_actions  (optionally → communications)
              └─< resolution_reviews ──▶ evidence (follow-up photo)
```

`─<` means one-to-many. Every complaint-owned table has `complaint_id` with `ON DELETE CASCADE`.

## 2. Tables

### `users` (Milestone 1)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(120) NOT NULL | |
| email | VARCHAR(254) NOT NULL | stored lower-cased; **unique index** |
| password_hash | VARCHAR(255) NOT NULL | Argon2 hash. The plain password is never stored or logged. |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| notification_preferences | JSONB NOT NULL DEFAULT '{}' | e.g. `{"followup_ready": true, "status_changes": true}` |
| privacy_settings | JSONB NOT NULL DEFAULT '{}' | e.g. `{"include_name_in_complaints": true, "share_exact_coordinates": true}` |
| notifications_last_seen_at | TIMESTAMPTZ NULL | unread notifications = events after this time |
| last_login_at | TIMESTAMPTZ NULL | |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | |

### `user_sessions` (Milestone 1)
Added on top of the original spec, because server-side sessions give real logout and revocation.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users ON DELETE CASCADE | indexed |
| token_hash | CHAR(64) NOT NULL UNIQUE | SHA-256 of the random cookie token. The raw token is never stored. |
| expires_at | TIMESTAMPTZ NOT NULL | |
| last_used_at | TIMESTAMPTZ NULL | |
| revoked_at | TIMESTAMPTZ NULL | set on logout |
| user_agent | VARCHAR(255) NULL | truncated; for the "active sessions" view later |
| created_at | TIMESTAMPTZ NOT NULL | |

### `complaints` (Milestone 2)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| public_reference | VARCHAR(20) NOT NULL UNIQUE | human-friendly ID, e.g. `CP-2026-000123`, numbered by the `complaint_reference_seq` sequence |
| user_id | UUID FK → users ON DELETE CASCADE | |
| title | VARCHAR(160) NULL | nullable while still a draft |
| description | TEXT NULL | |
| category | VARCHAR(40) NULL | `Category` enum |
| severity | VARCHAR(20) NULL | `LOW`, `MEDIUM`, `HIGH`, `UNKNOWN`. Confirmed by the citizen, not the AI. |
| status | VARCHAR(40) NOT NULL DEFAULT 'DRAFT' | CHECK constraint on allowed values |
| address_line | VARCHAR(255) NULL | |
| locality | VARCHAR(120) NULL | neighbourhood / ward |
| city | VARCHAR(120) NULL | used for authority matching |
| state | VARCHAR(120) NULL | |
| postal_code | VARCHAR(20) NULL | |
| country | VARCHAR(2) NULL | ISO-3166 alpha-2 |
| latitude / longitude | NUMERIC(9,6) NULL | CHECK range −90..90 / −180..180 |
| location_confirmed_at | TIMESTAMPTZ NULL | set when the citizen confirms the location |
| observed_at | TIMESTAMPTZ NULL | when the citizen saw the problem (user-provided) |
| draft_subject | VARCHAR(200) NULL | the complaint letter's subject (M3: AI- or template-drafted, then edited by the citizen) |
| draft_body | TEXT NULL | the complaint letter's text |
| authority_id | UUID FK → authorities ON DELETE SET NULL, NULL | the selected department (M4), indexed |
| authority_reference_number | VARCHAR(100) NULL | extracted from a department reply |
| acknowledged_at | TIMESTAMPTZ NULL | |
| last_response_at | TIMESTAMPTZ NULL | last inbound communication |
| submitted_at | TIMESTAMPTZ NULL | when the submission was **accepted by the provider** |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | |

Constraints: `CHECK` on `status` values and on latitude/longitude ranges. Indexes: `(user_id, created_at)`, `(user_id, status)`, `(category)`.

### `evidence` (Milestone 2)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed |
| evidence_type | VARCHAR(20) NOT NULL | `ORIGINAL` (the problem; while a draft) or `FOLLOWUP` (an "after" photo, M6; at most 5) |
| file_storage_key | VARCHAR(255) NOT NULL | opaque key for `StorageService`, e.g. `complaints/<id>/<uuid>.jpg` |
| file_type | VARCHAR(50) NOT NULL | MIME type detected by Pillow (not trusted from the client) |
| file_size_bytes | INTEGER NOT NULL | |
| width / height | INTEGER NULL | |
| checksum | VARCHAR(64) NOT NULL | SHA-256 of the **stored** (cleaned) file. `UNIQUE (complaint_id, checksum)` stops the same photo being attached twice. |
| created_at | TIMESTAMPTZ NOT NULL | |

### `authorities` (Milestone 4) ✅
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(200) NOT NULL | official department name; UNIQUE with `(city, state, country)` |
| jurisdiction | VARCHAR(200) NOT NULL | display text, e.g. "Ward 12, Example City" |
| jurisdiction_level | VARCHAR(20) NOT NULL | CHECK: `WARD`, `CITY`, `DISTRICT`, `STATE`, `NATIONAL` |
| city / state | VARCHAR(120) NULL | compared case-insensitively when matching; `city` indexed |
| country | VARCHAR(2) NOT NULL | ISO-2 (`XX` for the fictional demo city) |
| supported_categories | VARCHAR(40)[] NOT NULL DEFAULT `{}` | **GIN index**. Empty = escalation-only office. |
| official_email | VARCHAR(254) NULL | only if verified |
| official_phone | VARCHAR(40) NULL | only if verified |
| website_url | VARCHAR(500) NULL | |
| source_url | VARCHAR(500) NULL | official page where the contact was found |
| verified_at | DATE NULL | the day a person last checked the source |
| verification_notes | TEXT NULL | e.g. where on the page the contact is listed |
| service_timeline_days | INTEGER NULL | official response timeline, **only if a source states it** |
| parent_authority_id | UUID FK → authorities ON DELETE SET NULL | next escalation level |
| is_demo | BOOLEAN NOT NULL DEFAULT false | `true` for fictional demo records |
| active | BOOLEAN NOT NULL DEFAULT true | inactive departments are never matched or selectable |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | |

**CHECK `real_records_are_source_backed`:** `is_demo OR (source_url IS NOT NULL AND verified_at IS NOT NULL)`. The database itself refuses a real department without a source and a verification date.

### `ai_analyses` (Milestone 3) ✅
One row per AI call, successful or failed, so every result can be traced to the exact provider, model, and prompt.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed `(complaint_id, analysis_type, created_at)` |
| analysis_type | VARCHAR(40) NOT NULL | CHECK: `VISION`, `COMPLAINT_DRAFT`, `REPLY_CLASSIFICATION`, `FOLLOWUP_DRAFT` (M5), `RESOLUTION` (M6; `evidence_id` = the after photo) |
| evidence_id | UUID FK → evidence ON DELETE SET NULL | the analysed photo |
| provider | VARCHAR(40) NOT NULL | `mock`, `anthropic` |
| model | VARCHAR(80) NOT NULL | e.g. `claude-opus-5-5` (as reported by the API), `mock-v1` |
| prompt_version | VARCHAR(40) NOT NULL | e.g. `vision.v1`, `complaint_letter.v1` |
| is_mock | BOOLEAN NOT NULL | demo output; the UI shows "Demo AI" |
| status | VARCHAR(20) NOT NULL | CHECK: `SUCCEEDED`, `FAILED` |
| structured_result | JSONB NULL | the validated, sanitised output |
| error_code | VARCHAR(40) NULL | `PROVIDER_ERROR`, `TIMEOUT`, `RATE_LIMITED`, `REFUSED`, `INVALID_OUTPUT` |
| error_message | VARCHAR(500) NULL | short, safe (never contains secrets) |
| latency_ms | INTEGER NULL | |
| input_tokens / output_tokens | INTEGER NULL | reported by real providers |
| created_at | TIMESTAMPTZ NOT NULL | |

M5 added `communication_id` (UUID FK → communications ON DELETE SET NULL): the reply a `REPLY_CLASSIFICATION` read.

### `communications` (Milestone 4) ✅
An outgoing row is a **snapshot of exactly what the citizen approved**. It is never edited afterwards; a changed complaint gets a new approval (a new row).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed `(complaint_id, created_at)` |
| authority_id | UUID FK → authorities ON DELETE SET NULL | the department it was addressed to |
| seq | BIGINT IDENTITY UNIQUE | insertion order (M5): Windows' clock can give two rows the same `created_at` |
| direction | VARCHAR(10) NOT NULL | CHECK: `OUTBOUND`, `INBOUND` |
| communication_type | VARCHAR(20) NOT NULL | CHECK: `COMPLAINT`, `FOLLOW_UP` (reminder), `REPLY` (from the department) |
| channel | VARCHAR(20) NOT NULL | `EMAIL` (later: `PORTAL`, `MANUAL`) |
| recipient / sender | VARCHAR(254) NULL | |
| subject | VARCHAR(255) NOT NULL | |
| body | TEXT NOT NULL | plain text |
| attachments | JSONB NOT NULL DEFAULT `[]` | `[{evidence_id, file_type}]`: references to the cleaned photos (their ids are part of the content hash) |
| delivery_status | VARCHAR(30) NOT NULL | CHECK: `DRAFT` (reminder awaiting approval), `APPROVED`, `SENDING`, `SENT`, `SIMULATED_SENT`, `FAILED`, `SUPERSEDED`, `CANCELLED` (reminder not sent), `RECEIVED` (reply) |
| is_simulated | BOOLEAN NOT NULL | true for every mock send. **The UI always shows it.** |
| provider | VARCHAR(40) NULL | `mock` (later: `gmail`) |
| provider_message_id | VARCHAR(255) NULL | |
| idempotency_key | VARCHAR(120) UNIQUE NULL | `complaint:<id>:v<n>`; also passed to the provider |
| content_sha256 | VARCHAR(64) NULL | SHA-256 of recipient + subject + body + attachments, as approved |
| approval_details | JSONB NULL | `{"approved_by", "approved_at", "content_sha256", "recipient"}` |
| attempt_count | INTEGER NOT NULL DEFAULT 0 | send attempts (retries after `FAILED`) |
| error_message | VARCHAR(500) NULL | short, safe text from the last failure |
| sent_at / received_at | TIMESTAMPTZ NULL | |
| followup_number | INTEGER NULL | reminders: 1, 2, … (M5) |
| reply_kind | VARCHAR(30) NULL | replies: CHECK `ACKNOWLEDGMENT`, `IN_PROGRESS`, `RESOLVED_CLAIM`, `REQUEST_FOR_INFO`, `REJECTION`, `UNRELATED`. NULL = the citizen still has to say (M5) |
| reply_kind_source | VARCHAR(20) NULL | `AI` or `CITIZEN` |
| reply_summary | VARCHAR(500) NULL | the AI's sanitised one-line summary |
| reference_number | VARCHAR(40) NULL | the department's reference **found word-for-word** in this reply |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | |

Reminder rows use `idempotency_key` = `followup:<scheduled_action_id>`: one draft per check, ever.

**CHECK `simulated_never_sent`:** `NOT (is_simulated AND delivery_status = 'SENT')`. A simulated message can never be recorded as really delivered.

### `complaint_events` (Milestone 2)
An **append-only** audit trail. It powers the timeline, the activity feed, and notifications.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed `(complaint_id, created_at, seq)` |
| seq | BIGINT IDENTITY UNIQUE | insertion order; breaks ties when events share a timestamp |
| event_type | VARCHAR(50) NOT NULL | see `docs/workflows.md` §3 |
| previous_status / new_status | VARCHAR(40) NULL | filled when the event changed status |
| description | VARCHAR(500) NOT NULL | human-readable |
| actor | VARCHAR(20) NOT NULL | `CITIZEN`, `SYSTEM`, `AI`, `AUTHORITY` |
| metadata | JSONB NOT NULL DEFAULT '{}' | e.g. `{"evidence_id": "..."}`. The Python attribute is `details`, because SQLAlchemy reserves `metadata`. |
| created_at | TIMESTAMPTZ NOT NULL | |

### `scheduled_actions` (Milestone 5) ✅
The worker's to-do list. An action never sends anything: at most it drafts a reminder or records an escalation recommendation.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed `(complaint_id, created_at)` |
| action_type | VARCHAR(40) NOT NULL | CHECK: `FOLLOWUP_CHECK` |
| scheduled_at | TIMESTAMPTZ NOT NULL | the deadline (department's listed response time, or the defaults) |
| execution_status | VARCHAR(20) NOT NULL | CHECK: `PENDING`, `RUNNING`, `DONE`, `SKIPPED`, `FAILED`, `CANCELLED` |
| attempt_count | INTEGER NOT NULL DEFAULT 0 | retries back off 5, 10, 20… minutes; `FAILED` after `SCHEDULER_MAX_ATTEMPTS` |
| idempotency_key | VARCHAR(120) NOT NULL **UNIQUE** | `followup_check:<complaint_id>:after:<communication_id>`: one check per message |
| payload | JSONB NOT NULL DEFAULT '{}' | `{trigger, after_communication_id, basis, official}` (`basis` is the plain-language reason for the date) |
| outcome | VARCHAR(300) NULL | what happened, e.g. "Reminder 1 drafted. Nothing was sent." |
| last_error | VARCHAR(500) NULL | |
| executed_at | TIMESTAMPTZ NULL | |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | `updated_at` also detects a run that got stuck (`RUNNING` > 15 min) |

Partial index `ix_scheduled_actions_pending_due`: `(scheduled_at) WHERE execution_status = 'PENDING'` (the worker's query).

### `resolution_reviews` (Milestone 6) ✅
One check of a repair: an "after" photo, the AI's comparison (advice), and the citizen's decision. Rows are never deleted or rewritten after the decision: this is the audited resolution history.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| seq | BIGINT IDENTITY UNIQUE | order of the history |
| complaint_id | UUID FK → complaints ON DELETE CASCADE | indexed |
| followup_evidence_id | UUID FK → evidence ON DELETE CASCADE, **UNIQUE** | the "after" photo: one check per photo |
| original_evidence_id | UUID FK → evidence ON DELETE SET NULL | the "before" photo it was compared with |
| ai_analysis_id | UUID FK → ai_analyses ON DELETE SET NULL | the recorded AI call |
| ai_status | VARCHAR(20) NOT NULL | CHECK: `SUCCEEDED`, `FAILED` (the citizen compares alone) |
| ai_error_code | VARCHAR(40) NULL | e.g. `PROVIDER_ERROR`, `INVALID_OUTPUT`, `NO_ORIGINAL_PHOTO` |
| ai_assessment | JSONB NULL | validated, sanitised `ResolutionAssessment` snapshot |
| is_mock | BOOLEAN NOT NULL | "Demo AI" |
| decision | VARCHAR(30) NOT NULL DEFAULT 'PENDING' | CHECK: `PENDING`, `CONFIRMED_RESOLVED`, `DISPUTED`, `SUPERSEDED` (a newer photo replaced it) |
| citizen_notes | TEXT NULL | ≤ 1000 chars (API) |
| decided_at | TIMESTAMPTZ NULL | CHECK `decided_has_time`: a decision always has a time |
| decided_by | UUID FK → users ON DELETE SET NULL | |
| created_at / updated_at | TIMESTAMPTZ NOT NULL | |

Partial unique index `uq_resolution_reviews_one_pending`: `(complaint_id) WHERE decision = 'PENDING'`, so at most one check per complaint waits for a decision.

## 3. Deliberately *not* added (yet)

- **No `notifications` table.** Notifications come from `complaint_events` plus `users.notifications_last_seen_at`. Add a table only when per-notification read state or email/push delivery is needed.
- **No `categories` table.** Categories are a code enum; that's easier to keep consistent with prompts and icons.
- **No PostGIS.** Matching uses `city`/`state` text plus coordinates kept for future geo-fencing.

## 4. Adding verified authorities

The directory must never contain invented contacts. **No real records ship with the project**; add them yourself with the importer. For each real record:

1. Find the department on an **official government website** (e.g. a municipal corporation's grievance page).
2. Copy the name, email, and phone **exactly** into a JSON file shaped like `docs/authorities.example.json`. Put the page URL in `source_url` and the day you checked it in `verified_at`.
3. Fill `service_timeline_days` only if an official citizen charter or service-level document states it.
4. Check the file: `python -m scripts.import_authorities my-authorities.json` (from `backend/`). It refuses non-https sources, verification dates in the future or over a year old, reserved demo email domains (`.example`, `.test`, `.invalid`), unknown categories, and unknown fields. Nothing is written yet.
5. Write it: add `--apply`. Records are saved with `is_demo = false`; importing the same department again (same name and place) updates it. `parent_name` links an escalation office from the same file.

Adding real records does **not** enable real sending: submissions stay simulated (see `ALLOW_REAL_SUBMISSIONS` in `docs/development.md`).

Demo seed records use `is_demo = true`, reserved `.example` email domains (RFC 2606), and fictional names, so they can never reach a real inbox. The UI shows a "Demo directory entry" badge for them.

## 5. Migrations workflow

```bash
cd backend
alembic revision --autogenerate -m "add complaints table"   # creates a file in alembic/versions/
# READ the generated file and fix anything autogenerate missed (CHECK constraints, partial indexes)
alembic upgrade head
alembic downgrade -1   # undo the last migration if needed
```
