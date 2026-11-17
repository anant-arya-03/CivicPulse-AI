# CivicPulse AI: implementation inventory

Snapshot: 17 November 2026. Generated from the currently imported SQLAlchemy models, FastAPI OpenAPI document, complaint status machine and Pydantic AI schemas. Read with the [presentation guide](presentation-guide.md). No private account data or secrets are included.

## 1. Database columns

This is the application model inventory, with SQL types compiled for PostgreSQL, not a fresh migration-drift test. UUID primary keys identify records; nullable means the column can be empty. Common timestamp fields are included rather than hidden.

### `authorities`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `name` | `VARCHAR(200)` | no |  |
| `jurisdiction` | `VARCHAR(200)` | no |  |
| `jurisdiction_level` | `VARCHAR(20)` | no |  |
| `city` | `VARCHAR(120)` | yes |  |
| `state` | `VARCHAR(120)` | yes |  |
| `country` | `VARCHAR(2)` | no |  |
| `supported_categories` | `VARCHAR(40)[]` | no | DB default: {} |
| `official_email` | `VARCHAR(254)` | yes |  |
| `official_phone` | `VARCHAR(40)` | yes |  |
| `website_url` | `VARCHAR(500)` | yes |  |
| `source_url` | `VARCHAR(500)` | yes |  |
| `verified_at` | `DATE` | yes |  |
| `verification_notes` | `TEXT` | yes |  |
| `service_timeline_days` | `INTEGER` | yes |  |
| `parent_authority_id` | `UUID` | yes | FK -> authorities.id |
| `is_demo` | `BOOLEAN` | no | application default: False |
| `active` | `BOOLEAN` | no | DB default: true; application default: True |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_authorities_jurisdiction_level_valid`: `jurisdiction_level IN ('WARD', 'CITY', 'DISTRICT', 'STATE', 'NATIONAL')`
- CHECK `ck_authorities_real_records_are_source_backed`: `is_demo OR (source_url IS NOT NULL AND verified_at IS NOT NULL)`
- UNIQUE: `name`, `city`, `state`, `country`
- Indexes: `ix_authorities_city` on (city); `ix_authorities_supported_categories` on (supported_categories)

### `users`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `name` | `VARCHAR(120)` | no |  |
| `email` | `VARCHAR(254)` | no | unique |
| `password_hash` | `VARCHAR(255)` | no |  |
| `is_active` | `BOOLEAN` | no | DB default: true; application default: True |
| `notification_preferences` | `JSONB` | no | DB default: {} |
| `privacy_settings` | `JSONB` | no | DB default: {} |
| `notifications_last_seen_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `notifications_last_seen_seq` | `BIGINT` | no | DB default: 0; application default: 0 |
| `last_login_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_users_email_lowercase`: `email = lower(email)`
- UNIQUE: `email`

### `complaints`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `public_reference` | `VARCHAR(20)` | no | unique |
| `user_id` | `UUID` | no | FK -> users.id |
| `title` | `VARCHAR(160)` | yes |  |
| `description` | `TEXT` | yes |  |
| `category` | `VARCHAR(40)` | yes |  |
| `severity` | `VARCHAR(20)` | yes |  |
| `status` | `VARCHAR(40)` | no | application default: DRAFT |
| `address_line` | `VARCHAR(255)` | yes |  |
| `locality` | `VARCHAR(120)` | yes |  |
| `city` | `VARCHAR(120)` | yes |  |
| `state` | `VARCHAR(120)` | yes |  |
| `postal_code` | `VARCHAR(20)` | yes |  |
| `country` | `VARCHAR(2)` | yes |  |
| `latitude` | `NUMERIC(9, 6)` | yes |  |
| `longitude` | `NUMERIC(9, 6)` | yes |  |
| `location_confirmed_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `observed_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `draft_subject` | `VARCHAR(200)` | yes |  |
| `draft_body` | `TEXT` | yes |  |
| `authority_id` | `UUID` | yes | FK -> authorities.id |
| `authority_reference_number` | `VARCHAR(100)` | yes |  |
| `acknowledged_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `last_response_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `submitted_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_complaints_latitude_range`: `latitude IS NULL OR latitude BETWEEN -90 AND 90`
- CHECK `ck_complaints_longitude_range`: `longitude IS NULL OR longitude BETWEEN -180 AND 180`
- CHECK `ck_complaints_status_valid`: `status IN ('DRAFT', 'PENDING_REVIEW', 'SUBMITTED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED_PENDING_VERIFICATION', 'VERIFIED_RESOLVED', 'CLOSED', 'REOPENED', 'CANCELLED')`
- UNIQUE: `public_reference`
- Indexes: `ix_complaints_authority_id` on (authority_id); `ix_complaints_category` on (category); `ix_complaints_user_created` on (user_id, created_at); `ix_complaints_user_status` on (user_id, status)

### `user_sessions`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `user_id` | `UUID` | no | FK -> users.id |
| `token_hash` | `VARCHAR(64)` | no | unique |
| `expires_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `last_used_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `revoked_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `user_agent` | `VARCHAR(255)` | yes |  |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `id` | `UUID` | no | primary key |

- UNIQUE: `token_hash`
- Indexes: `ix_user_sessions_user_id` on (user_id)

### `communications`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `seq` | `BIGINT` | no | unique |
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `authority_id` | `UUID` | yes | FK -> authorities.id |
| `direction` | `VARCHAR(10)` | no |  |
| `communication_type` | `VARCHAR(20)` | no |  |
| `channel` | `VARCHAR(20)` | no | application default: EMAIL |
| `recipient` | `VARCHAR(254)` | yes |  |
| `sender` | `VARCHAR(254)` | yes |  |
| `subject` | `VARCHAR(255)` | no |  |
| `body` | `TEXT` | no |  |
| `attachments` | `JSONB` | no | DB default: [] |
| `delivery_status` | `VARCHAR(30)` | no |  |
| `is_simulated` | `BOOLEAN` | no |  |
| `provider` | `VARCHAR(40)` | yes |  |
| `provider_message_id` | `VARCHAR(255)` | yes |  |
| `idempotency_key` | `VARCHAR(120)` | yes | unique |
| `content_sha256` | `VARCHAR(64)` | yes |  |
| `approval_details` | `JSONB` | yes |  |
| `attempt_count` | `INTEGER` | no | application default: 0 |
| `error_message` | `VARCHAR(500)` | yes |  |
| `sent_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `received_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `followup_number` | `INTEGER` | yes |  |
| `reply_kind` | `VARCHAR(30)` | yes |  |
| `reply_kind_source` | `VARCHAR(20)` | yes |  |
| `reply_summary` | `VARCHAR(500)` | yes |  |
| `reference_number` | `VARCHAR(40)` | yes |  |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_communications_delivery_status_valid`: `delivery_status IN ('DRAFT', 'APPROVED', 'SENDING', 'SENT', 'SIMULATED_SENT', 'FAILED', 'SUPERSEDED', 'CANCELLED', 'RECEIVED')`
- CHECK `ck_communications_direction_valid`: `direction IN ('OUTBOUND', 'INBOUND')`
- CHECK `ck_communications_reply_kind_valid`: `reply_kind IS NULL OR reply_kind IN ('ACKNOWLEDGMENT', 'IN_PROGRESS', 'RESOLVED_CLAIM', 'REQUEST_FOR_INFO', 'REJECTION', 'UNRELATED')`
- CHECK `ck_communications_simulated_never_sent`: `NOT (is_simulated AND delivery_status = 'SENT')`
- CHECK `ck_communications_type_valid`: `communication_type IN ('COMPLAINT', 'FOLLOW_UP', 'REPLY')`
- UNIQUE: `idempotency_key`
- UNIQUE: `seq`
- Indexes: `ix_communications_complaint_created` on (complaint_id, created_at)

### `complaint_events`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `seq` | `BIGINT` | no | unique |
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `event_type` | `VARCHAR(50)` | no |  |
| `previous_status` | `VARCHAR(40)` | yes |  |
| `new_status` | `VARCHAR(40)` | yes |  |
| `description` | `VARCHAR(500)` | no |  |
| `actor` | `VARCHAR(20)` | no |  |
| `metadata` | `JSONB` | no | DB default: {} |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `id` | `UUID` | no | primary key |

- UNIQUE: `seq`
- Indexes: `ix_complaint_events_complaint_created` on (complaint_id, created_at, seq)

### `evidence`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `evidence_type` | `VARCHAR(20)` | no |  |
| `file_storage_key` | `VARCHAR(255)` | no |  |
| `file_type` | `VARCHAR(50)` | no |  |
| `file_size_bytes` | `INTEGER` | no |  |
| `width` | `INTEGER` | yes |  |
| `height` | `INTEGER` | yes |  |
| `checksum` | `VARCHAR(64)` | no |  |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `id` | `UUID` | no | primary key |

- CHECK `ck_evidence_evidence_type_valid`: `evidence_type IN ('ORIGINAL', 'FOLLOWUP')`
- UNIQUE: `complaint_id`, `checksum`
- Indexes: `ix_evidence_complaint_id` on (complaint_id)

### `scheduled_actions`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `action_type` | `VARCHAR(40)` | no |  |
| `scheduled_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `execution_status` | `VARCHAR(20)` | no | application default: PENDING |
| `attempt_count` | `INTEGER` | no | application default: 0 |
| `idempotency_key` | `VARCHAR(120)` | no | unique |
| `payload` | `JSONB` | no | DB default: {} |
| `outcome` | `VARCHAR(300)` | yes |  |
| `last_error` | `VARCHAR(500)` | yes |  |
| `executed_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_scheduled_actions_action_type_valid`: `action_type IN ('FOLLOWUP_CHECK')`
- CHECK `ck_scheduled_actions_execution_status_valid`: `execution_status IN ('PENDING', 'RUNNING', 'DONE', 'SKIPPED', 'FAILED', 'CANCELLED')`
- UNIQUE: `idempotency_key`
- Indexes: `ix_scheduled_actions_complaint` on (complaint_id, created_at); `ix_scheduled_actions_pending_due` on (scheduled_at)

### `ai_analyses`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `analysis_type` | `VARCHAR(40)` | no |  |
| `evidence_id` | `UUID` | yes | FK -> evidence.id |
| `communication_id` | `UUID` | yes | FK -> communications.id |
| `provider` | `VARCHAR(40)` | no |  |
| `model` | `VARCHAR(80)` | no |  |
| `prompt_version` | `VARCHAR(40)` | no |  |
| `is_mock` | `BOOLEAN` | no |  |
| `status` | `VARCHAR(20)` | no |  |
| `structured_result` | `JSONB` | yes |  |
| `error_code` | `VARCHAR(40)` | yes |  |
| `error_message` | `VARCHAR(500)` | yes |  |
| `latency_ms` | `INTEGER` | yes |  |
| `input_tokens` | `INTEGER` | yes |  |
| `output_tokens` | `INTEGER` | yes |  |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `id` | `UUID` | no | primary key |

- CHECK `ck_ai_analyses_analysis_type_valid`: `analysis_type IN ('VISION', 'COMPLAINT_DRAFT', 'REPLY_CLASSIFICATION', 'FOLLOWUP_DRAFT', 'RESOLUTION')`
- CHECK `ck_ai_analyses_status_valid`: `status IN ('SUCCEEDED', 'FAILED')`
- Indexes: `ix_ai_analyses_complaint_type_created` on (complaint_id, analysis_type, created_at)

### `resolution_reviews`

| Column | SQL type | Nullable | Keys / declared defaults |
|---|---|---|---|
| `seq` | `BIGINT` | no | unique |
| `complaint_id` | `UUID` | no | FK -> complaints.id |
| `followup_evidence_id` | `UUID` | no | unique; FK -> evidence.id |
| `original_evidence_id` | `UUID` | yes | FK -> evidence.id |
| `ai_analysis_id` | `UUID` | yes | FK -> ai_analyses.id |
| `ai_status` | `VARCHAR(20)` | no |  |
| `ai_error_code` | `VARCHAR(40)` | yes |  |
| `ai_assessment` | `JSONB` | yes |  |
| `is_mock` | `BOOLEAN` | no | application default: False |
| `decision` | `VARCHAR(30)` | no | application default: PENDING |
| `citizen_notes` | `TEXT` | yes |  |
| `decided_at` | `TIMESTAMP WITH TIME ZONE` | yes |  |
| `decided_by` | `UUID` | yes | FK -> users.id |
| `id` | `UUID` | no | primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |  |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |  |

- CHECK `ck_resolution_reviews_ai_status_valid`: `ai_status IN ('SUCCEEDED', 'FAILED')`
- CHECK `ck_resolution_reviews_decided_has_time`: `decision IN ('PENDING', 'SUPERSEDED') OR decided_at IS NOT NULL`
- CHECK `ck_resolution_reviews_decision_valid`: `decision IN ('PENDING', 'CONFIRMED_RESOLVED', 'DISPUTED', 'SUPERSEDED')`
- UNIQUE: `followup_evidence_id`
- UNIQUE: `seq`
- Indexes: `ix_resolution_reviews_complaint_id` on (complaint_id); `uq_resolution_reviews_one_pending` on (complaint_id)

## 2. API operations

All paths below are under `/api/v1`. The local interactive contract is at `http://localhost:8000/docs` while the backend runs. Almost all operations require a session; health and account-entry routes are exceptions. State-changing authenticated requests require CSRF. The simulation-info endpoint requires login; mutation endpoints also require simulation to be enabled.

| Method | Path | Operation summary | Request body schema |
|---|---|---|---|
| GET | `/health` | Health | none |
| POST | `/auth/register` | Register | RegisterRequest (application/json) |
| POST | `/auth/login` | Login | LoginRequest (application/json) |
| POST | `/auth/logout` | Logout | none |
| GET | `/auth/me` | Me | none |
| PATCH | `/users/me` | Update Me | UserUpdate (application/json) |
| PUT | `/users/me/settings` | Settings | SettingsUpdate (application/json) |
| POST | `/users/me/password` | Password | PasswordChange (application/json) |
| POST | `/complaints` | Create Complaint | inline schema (application/json) |
| GET | `/complaints` | List Complaints | none |
| GET | `/complaints/{complaint_id}` | Get Complaint | none |
| PATCH | `/complaints/{complaint_id}` | Update Complaint | ComplaintUpdate (application/json) |
| POST | `/complaints/{complaint_id}/cancel` | Cancel Complaint | none |
| POST | `/complaints/{complaint_id}/close` | Close Complaint | none |
| GET | `/complaints/{complaint_id}/timeline` | Get Timeline | none |
| POST | `/complaints/{complaint_id}/evidence` | Upload Evidence | Body_upload_evidence_api_v1_complaints__complaint_id__evidence_post (multipart/form-data) |
| POST | `/complaints/{complaint_id}/followup-evidence` | Upload Followup Evidence | Body_upload_followup_evidence_api_v1_complaints__complaint_id__followup_evidence_post (multipart/form-data) |
| GET | `/evidence/{evidence_id}/file` | Get Evidence File | none |
| DELETE | `/evidence/{evidence_id}` | Delete Evidence | none |
| GET | `/dashboard/summary` | Dashboard Summary | none |
| GET | `/locations/search` | Search Locations | none |
| GET | `/locations/reverse` | Reverse Geocode | none |
| POST | `/complaints/{complaint_id}/analysis` | Analyze Photo | inline schema (application/json) |
| GET | `/complaints/{complaint_id}/analysis` | Latest Analysis | none |
| POST | `/complaints/{complaint_id}/complaint-draft` | Generate Complaint Draft | ComplaintDraftRequest (application/json) |
| GET | `/authorities` | List Authorities | none |
| GET | `/authorities/{authority_id}` | Get Authority | none |
| GET | `/complaints/{complaint_id}/authority-matches` | Authority Matches | none |
| PUT | `/complaints/{complaint_id}/authority` | Select Authority | SelectAuthorityRequest (application/json) |
| GET | `/complaints/{complaint_id}/submission-preview` | Submission Preview | none |
| POST | `/complaints/{complaint_id}/approve` | Approve | ApproveRequest (application/json) |
| POST | `/communications/{communication_id}/send` | Send | none |
| GET | `/complaints/{complaint_id}/communications` | List Communications | none |
| PATCH | `/communications/{communication_id}` | Update Followup | FollowupUpdate (application/json) |
| POST | `/communications/{communication_id}/approve` | Approve Followup | ApproveRequest (application/json) |
| POST | `/communications/{communication_id}/dismiss` | Dismiss Followup | none |
| GET | `/complaints/{complaint_id}/monitoring` | Monitoring | none |
| PUT | `/communications/{communication_id}/reply-kind` | Set Reply Kind | ReplyKindRequest (application/json) |
| GET | `/simulation` | Simulation Info | none |
| POST | `/complaints/{complaint_id}/simulation/reply` | Simulate Reply | SimulateReplyRequest (application/json) |
| POST | `/complaints/{complaint_id}/simulation/advance` | Advance | none |
| POST | `/complaints/{complaint_id}/resolution-reviews` | Create Review | CreateReviewRequest (application/json) |
| GET | `/complaints/{complaint_id}/resolution-reviews` | List Reviews | none |
| POST | `/resolution-reviews/{review_id}/decision` | Decide | DecisionRequest (application/json) |
| POST | `/complaints/{complaint_id}/reopen` | Reopen | ReopenRequest (application/json) |
| GET | `/notifications` | Notifications | none |
| POST | `/notifications/mark-seen` | Mark Seen | MarkSeen (application/json) |

Current inventory: **47 HTTP operations** across **43 paths**. An operation count is not a feature count.

The operation list distinguishes POST approval from POST send. The interface can expose an approve-and-send action, but the backend retains separate approval and delivery checks.

### Common responses

| Status | Typical meaning |
|---|---|
| 200 / 201 / 204 | Successful read/update, creation or no-content action, depending on route. |
| 401 | Missing, expired or revoked session. |
| 403 | Security/CSRF or real-send guard, depending on operation. |
| 404 | Missing resource, another user's private resource, or disabled simulation mutation. |
| 409 | State conflict, changed content, duplicate evidence or similar workflow conflict. |
| 413 | Upload too large when handled by the relevant backend size check. |
| 422 | Invalid input or missing business prerequisites. |
| 429 | Route rate limit reached. |
| 503 | Provider/database-dependent service unavailable, as handled by the endpoint. |

Domain errors are normalized into `{"error": {"code", "message", "details"}}`. Consult the endpoint/schema for the exact code; not every operation returns every status above.

## 3. Complete complaint transition table

A row lists allowed destinations, not automatic transitions. Services still enforce actor, ownership and prerequisite rules. Only citizen decisions can establish verified resolution.

| From | Allowed to |
|---|---|
| `DRAFT` | `CANCELLED`, `PENDING_REVIEW` |
| `PENDING_REVIEW` | `CANCELLED`, `DRAFT`, `SUBMITTED` |
| `SUBMITTED` | `ACKNOWLEDGED`, `CANCELLED`, `CLOSED`, `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION` |
| `ACKNOWLEDGED` | `CLOSED`, `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION` |
| `IN_PROGRESS` | `CLOSED`, `RESOLVED_PENDING_VERIFICATION` |
| `RESOLVED_PENDING_VERIFICATION` | `REOPENED`, `VERIFIED_RESOLVED` |
| `VERIFIED_RESOLVED` | `CLOSED`, `REOPENED` |
| `REOPENED` | `ACKNOWLEDGED`, `CLOSED`, `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION` |
| `CLOSED` | `REOPENED` |
| `CANCELLED` | none (terminal) |

## 4. Structured AI output fields

These schemas constrain output shape. Enum membership and string cleaning do not prove factual truth or calibrated confidence. Additional string/list sanitizers live in `backend/app/modules/ai/schemas.py` and `sanitize.py`.

### `VisionAnalysis`

| Field | Type / allowed values | Required | Description |
|---|---|---|---|
| `is_civic_issue` | boolean | yes | True only if the photo clearly shows a public infrastructure problem. |
| `category` | ROAD_POTHOLE/BROKEN_STREETLIGHT/GARBAGE_OVERFLOW/OPEN_DRAIN/WATER_LEAKAGE/WATERLOGGING/DAMAGED_INFRASTRUCTURE/OTHER | yes |  |
| `category_confidence` | HIGH/MEDIUM/LOW | yes |  |
| `suggested_title` | string | yes | A short neutral title, at most 120 characters. |
| `suggested_description` | string | yes | 2-3 factual sentences about what is visible, at most 800 characters. |
| `severity` | LOW/MEDIUM/HIGH/UNKNOWN | yes | Conservative. UNKNOWN when unsure. |
| `observations` | array of string | yes | Up to 6 short visible facts, each at most 200 characters. |
| `uncertainties` | array of string | yes | Up to 6 things that cannot be judged from the photo. |
| `warnings` | array of string | yes | Up to 4 notes for the reporter, e.g. people's faces are visible. |

### `ComplaintLetterProse`

| Field | Type / allowed values | Required | Description |
|---|---|---|---|
| `subject` | string | yes | Email subject line, at most 150 characters. |
| `issue_summary` | string | yes | 2-4 formal sentences describing the problem, using only the facts given. |
| `requested_action` | string | yes | 1-2 polite sentences saying what the citizen asks the department to do. |

### `ReplyClassification`

| Field | Type / allowed values | Required | Description |
|---|---|---|---|
| `kind` | ACKNOWLEDGMENT/IN_PROGRESS/RESOLVED_CLAIM/REQUEST_FOR_INFO/REJECTION/UNRELATED | yes | What the reply means for the complaint. |
| `confidence` | HIGH/MEDIUM/LOW | yes |  |
| `reference_number` | nullable / union | no | The department's reference number for the complaint, copied exactly, or null if the reply contains none. |
| `summary` | string | yes | One or two plain sentences: what the department said. |

### `FollowupProse`

| Field | Type / allowed values | Required | Description |
|---|---|---|---|
| `opening` | string | yes | 1-3 polite sentences saying the citizen is following up. |
| `requested_action` | string | yes | 1 polite sentence asking for an update or action. |

### `ResolutionAssessment`

| Field | Type / allowed values | Required | Description |
|---|---|---|---|
| `assessment` | APPEARS_RESOLVED/PARTIALLY_RESOLVED/NOT_RESOLVED/CANNOT_DETERMINE | yes |  |
| `confidence` | HIGH/MEDIUM/LOW | yes |  |
| `same_location_likely` | YES/NO/UNSURE | yes | Do both photos appear to show the same place? |
| `visible_changes` | array of string | yes | Up to 6 visible differences between the photos. |
| `remaining_problems` | array of string | yes | Up to 6 problems still visible in the second photo. |
| `uncertainties` | array of string | yes | Up to 6 things that cannot be judged from these photos. |
| `summary` | string | yes | 1-2 plain sentences. Say 'appears', never 'is definitely'. |

## 5. Agent request limits and records

| Detail | Implementation value |
|---|---|
| Vision / Writer / Resolution max output-token budget | 16,000 per request; a ceiling, not actual measured usage. |
| Monitoring classification / follow-up writing max budget | 8,000 per request. |
| Reply body sent to classification | First 8,000 characters; stored reply remains available for citizen review. |
| Real-adapter configured timeout | 90 seconds by default. |
| SDK client max retries | 2. |
| Image model-input long edge | At most 1,568 pixels, JPEG quality 85, aspect ratio preserved. |
| Prompt versions | Versioned modules for vision, complaint letter, reply classification, follow-up letter and resolution. |
| Audit data | Provider, model, prompt version, mock flag, success/failure, structured result, latency and token usage when available. |

Token budgets and timeout settings do not establish response speed or cost. No real-model latency, token-spend benchmark or accuracy benchmark was performed for this guide.
