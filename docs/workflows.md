# Workflows

> Status: the **status machine, events, all six report steps (M2–M4), the Vision and Complaint Letter agents (M3), department matching, and approval + simulated submission (M4), reply monitoring, reminders and escalation (M5), and resolution verification (M6) are implemented**.

## 1. Complaint lifecycle

```
                ┌──────────── cancel ────────────┐
                ▼                                │
 DRAFT ──citizen approves──▶ PENDING_REVIEW ──(send accepted)──▶ SUBMITTED
   ▲                          │                                             │
   └── edited: approval withdrawn ──┘                                       │
                                                                            ▼
                         ┌──────────────────────── ACKNOWLEDGED ◀───────────┤
                         │                              │                   │
                         ▼                              ▼                   │
                    IN_PROGRESS ─────────────▶ RESOLVED_PENDING_VERIFICATION◀┘
                                                   │              │
                                       citizen     │              │ citizen
                                       confirms    ▼              ▼ disputes
                                         VERIFIED_RESOLVED     REOPENED ──▶ (ACKNOWLEDGED / IN_PROGRESS /
                                                   │                          RESOLVED_PENDING_VERIFICATION / CLOSED)
                                                   ▼
                                                CLOSED ──reopen──▶ REOPENED
```

### Allowed transitions (single source of truth: `complaints/status_machine.py`)

| From | To |
|---|---|
| `DRAFT` | `PENDING_REVIEW`, `CANCELLED` |
| `PENDING_REVIEW` | `DRAFT`, `SUBMITTED`, `CANCELLED` |
| `SUBMITTED` | `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION`, `CLOSED`, `CANCELLED` |
| `ACKNOWLEDGED` | `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION`, `CLOSED` |
| `IN_PROGRESS` | `RESOLVED_PENDING_VERIFICATION`, `CLOSED` |
| `RESOLVED_PENDING_VERIFICATION` | `VERIFIED_RESOLVED`, `REOPENED` |
| `VERIFIED_RESOLVED` | `CLOSED`, `REOPENED` |
| `REOPENED` | `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED_PENDING_VERIFICATION`, `CLOSED` |
| `CLOSED` | `REOPENED` |
| `CANCELLED` | *(terminal)* |

Every status change goes through `ComplaintService.change_status(...)`. That one function validates the transition, updates the row, and writes a `complaint_events` row **in the same transaction**. Any other path is a bug.

### The milestones a citizen sees (and why they are different)

| What happened | Recorded as | Status change? |
|---|---|---|
| Draft saved | `DETAILS_UPDATED` event | stays `DRAFT` |
| Complaint letter generated | `COMPLAINT_DRAFT_GENERATED` | stays `DRAFT` |
| Department chosen | `AUTHORITY_SELECTED` (names a demo entry as such) | no |
| Citizen approved the exact message | `COMPLAINT_APPROVED`; communication `APPROVED` with `content_sha256` | → `PENDING_REVIEW` (shown as **"Ready to send"**) |
| Something changed after approval | `APPROVAL_WITHDRAWN` | → `DRAFT` |
| Submission attempted | `SUBMISSION_ATTEMPTED`; communication `SENDING` | no |
| Submission accepted by provider | `SUBMISSION_ACCEPTED`; communication `SENT` or `SIMULATED_SENT` | → `SUBMITTED` |
| Submission failed | `SUBMISSION_FAILED`; communication `FAILED` | stays `PENDING_REVIEW` (retry allowed) |
| Department replied | `REPLY_RECEIVED`, then `REPLY_CLASSIFIED` (AI or citizen) | depends on the meaning (§4, Agent 4) |
| Department acknowledged | `STATUS_CHANGED` (+ `REFERENCE_NUMBER_RECORDED`) | → `ACKNOWLEDGED` |
| Department claims it's fixed | `STATUS_CHANGED`, `FOLLOWUPS_STOPPED` | → `RESOLVED_PENDING_VERIFICATION` |
| No reply by the deadline | `FOLLOWUP_SUGGESTED`; reminder `DRAFT` | no |
| Citizen sent a reminder | `FOLLOWUP_APPROVED`, `FOLLOWUP_SENT` (or `FOLLOWUP_FAILED`) | no |
| Still no reply after the last reminder | `ESCALATION_RECOMMENDED` | no |
| Citizen adds an "after" photo | `RESOLUTION_EVIDENCE_UPLOADED`, then `RESOLUTION_ASSESSED` (AI advice) | no |
| Citizen confirms the fix | `RESOLUTION_CONFIRMED` (from a waiting status first `STATUS_CHANGED` → pending verification) | → `VERIFIED_RESOLVED` |
| Citizen says it isn't fixed | `RESOLUTION_DISPUTED`, `FOLLOWUP_SUGGESTED` ("not fixed" message draft) | → `REOPENED` |
| The problem came back | `COMPLAINT_REOPENED`, `FOLLOWUP_SUGGESTED` | → `REOPENED` |

> "Email sent" ≠ "department received it" ≠ "problem solved". The UI wording follows this table exactly.

## 2. Report-an-issue flow (frontend wizard ↔ backend)

| Step | UI | Backend calls | Notes |
|---|---|---|---|
| 1 Upload ✅ | drag-drop, preview, replace/remove, progress bar | `POST /complaints` (once) → `POST /complaints/{id}/evidence` | Upload uses XHR so progress can be shown. The server validates the file again. Replace uploads the new photo first, then removes the old one. |
| 2 AI analysis ✅ | Analysis starts automatically once per photo. "Looking at your photo…" (the form stays usable). Suggestions fill **only empty fields** ("Suggested by AI"); for fields the citizen filled, a different suggestion appears as "AI suggests: … Use suggestion". "Analyse again". | `GET`/`POST /complaints/{id}/analysis`, `PATCH /complaints/{id}` | On failure: warning banner, "Try again", and the form works by hand. Mock results carry a **"Demo AI"** label. |
| 3 Location ✅ | search (on submit), map pin (click or drag), "Use my current location", address form, "I confirm" checkbox | `GET /locations/search`, `GET /locations/reverse`, `PATCH /complaints/{id}` with `confirm_location: true` | Location comes only from the citizen; it is never guessed from the image. A pin only *suggests* an address; the citizen chooses "Use this address". |
| 4 Department ✅ (M4) | "Who should handle this?": matching departments as radio cards (jurisdiction, email, why it matched, source link + verification date, or a **"Demo directory entry"** badge); "Show other departments for this issue" | `GET /complaints/{id}/authority-matches`, `GET /authorities?category=`, `PUT /complaints/{id}/authority` | `EXACT` → pre-selected. `PARTIAL` → nothing pre-selected; the citizen must choose. `NONE` → "Continue without a department" (finish the letter and send it yourself). |
| 5 Letter ✅ (M3) | drafted automatically on first visit; editable subject + body; "Write it again with AI" (confirm: replaces your edits) | `POST /complaints/{id}/complaint-draft`, `PATCH /complaints/{id}` (`draft_subject`, `draft_body`) | On AI failure: "Use a basic template" (no AI) or "Try the AI again". With a department: "Save and continue" → step 6; without one: "Save complaint" opens the details page. |
| 6 Review & send ✅ (M4) | simulation notice; the exact message (from, to, subject, body, photos); checkbox "I have reviewed this complaint and approve sending it to …"; "Approve and send (simulated)" | `GET /complaints/{id}/submission-preview` → `POST /complaints/{id}/approve` (with the preview's hash) → `POST /communications/{id}/send` | Missing items are listed with buttons back to the right step. A failure shows "Try sending again" (the same approved message). Success opens the details page with **"Simulated submission complete. No email was sent to a real department."** |

**After sending (M5), the complaint page** shows *Response tracking*: the department's reference, "x of 2 reminders sent", the next deadline and why ("the response time listed for this department (7 days)" or CivicPulse's default), a reminder card when one is waiting (edit, approval checkbox, "Approve and send reminder (simulated)", "Don't send it", "Try sending again"), a "What does this reply mean?" card when the AI couldn't tell, and the escalation card. *Messages* lists every message both ways; simulated replies are labelled "Simulated reply: not from a real department". With `ENABLE_SIMULATION=true` a dashed *Demo tools* card offers simulated replies and "Skip ahead to the next check". The dashboard shows *Needs your attention*.

**Checking a repair (M6):** the *Check the repair* card (first on the page when the department says it's fixed; "Check the repair" in the status card jumps to it) takes an "after" photo (same drop zone and checks as step 1), shows *Uploading… / Comparing the photos…*, then **before and after side by side**, "The AI thinks: Appears repaired (medium confidence)" with a Demo AI badge, what it noticed, what's still visible, what it can't tell, and the warnings. The citizen chooses "Yes, it's fixed" or "No, it's not fixed" (only after a claimed repair), may add a note, ticks "I checked the place myself…", and saves. If the AI fails: "No AI comparison", "compare the two photos yourself", "Try the AI again", and the same decision form. *Earlier checks* keeps the history. A verified or closed complaint shows *Reopen complaint*.

The draft is saved on the server after every step, and the URL (`/report?draft=<id>&step=<n>`) remembers the position, so a refresh or a closed tab doesn't lose work. "Continue editing" on the details page reopens it.

## 3. Complaint event types

Implemented in M2: `COMPLAINT_CREATED`, `EVIDENCE_UPLOADED`, `EVIDENCE_REMOVED`, `DETAILS_UPDATED`, `LOCATION_CONFIRMED`, `COMPLAINT_CANCELLED`, `COMPLAINT_CLOSED` (`STATUS_CHANGED` reserved). M3: `AI_ANALYSIS_COMPLETED`, `AI_ANALYSIS_FAILED`, `COMPLAINT_DRAFT_GENERATED`. M4: `AUTHORITY_SELECTED`, `COMPLAINT_APPROVED`, `APPROVAL_WITHDRAWN`, `SUBMISSION_ATTEMPTED`, `SUBMISSION_ACCEPTED`, `SUBMISSION_FAILED`. M5: `REPLY_RECEIVED`, `REPLY_CLASSIFIED`, `REFERENCE_NUMBER_RECORDED`, `STATUS_CHANGED` (reply-driven), `FOLLOWUP_SUGGESTED`, `FOLLOWUP_APPROVED`, `FOLLOWUP_SENT`, `FOLLOWUP_FAILED`, `FOLLOWUP_DISMISSED`, `FOLLOWUPS_STOPPED`, `ESCALATION_RECOMMENDED`. M6: `RESOLUTION_EVIDENCE_UPLOADED`, `RESOLUTION_ASSESSED`, `RESOLUTION_CONFIRMED`, `RESOLUTION_DISPUTED`, `COMPLAINT_REOPENED`. Full original list: `AI_ANALYSIS_COMPLETED`, `AI_ANALYSIS_FAILED`, `DETAILS_UPDATED`, `LOCATION_CONFIRMED`, `AUTHORITY_SELECTED`, `COMPLAINT_DRAFT_GENERATED`, `COMPLAINT_APPROVED`, `SUBMISSION_ATTEMPTED`, `SUBMISSION_ACCEPTED`, `SUBMISSION_FAILED`, `REPLY_RECEIVED`, `REFERENCE_NUMBER_RECORDED`, `STATUS_CHANGED`, `FOLLOWUP_SUGGESTED`, `FOLLOWUP_APPROVED`, `FOLLOWUP_SENT`, `ESCALATION_RECOMMENDED`, `RESOLUTION_EVIDENCE_UPLOADED`, `RESOLUTION_ASSESSED`, `RESOLUTION_CONFIRMED`, `RESOLUTION_DISPUTED`, `COMPLAINT_CANCELLED`, `COMPLAINT_CLOSED`.

## 4. AI agents

All agents are plain Python classes in `backend/app/modules/ai/agents/`. Each one:

1. builds a prompt from a **versioned template** (`prompts/vision.v1.md` …),
2. calls `AIProvider.generate_structured(...)` with a **Pydantic output schema**,
3. gets back a validated object, or raises `AIOutputError` (invalid JSON or schema violation: retried once, then treated as failure),
4. is recorded in `ai_analyses` (provider, model, prompt_version, result) by `AIService`.

### Provider interface (sketch)

```python
class AIProvider(Protocol):
    name: str          # "mock" | "anthropic"
    model: str

    def generate_structured(
        self,
        *,
        task: AITask,                       # VISION, COMPLAINT_DRAFT, …
        system_prompt: str,
        content: list[TextPart | ImagePart],
        output_schema: type[T],             # a Pydantic model
        max_tokens: int,
    ) -> T: ...
```

- `MockAIProvider` returns deterministic sample data for each task. `MOCK_AI_SCENARIO` picks it (`pothole`, `streetlight`, `garbage`, `not_civic`, `failure`, `invalid`), and **every mock result is flagged `is_mock` so the UI can label it**. The mock does not look at the image.
- `AnthropicProvider` uses the official `anthropic` SDK: `client.beta.messages.parse(..., output_format=Schema, output_config={"effort": AI_EFFORT}, fallbacks="default")` → `response.parsed_output`. Images are downscaled to ≤ 1568 px and sent as base64 JPEG blocks. `stop_reason == "refusal"` (after the server-side fallback) → `REFUSED`; `max_tokens` → `INVALID_OUTPUT`. Default model `claude-opus-5-5` (`AI_MODEL`). The API key lives only in the backend's environment.

### Agent 1 — Vision agent (M3) ✅ `modules/ai/agents/vision_agent.py`, prompt `vision.v1`
Input: original photo. Output `VisionAnalysis`:
```json
{
  "is_civic_issue": true,
  "category": "ROAD_POTHOLE",
  "category_confidence": "HIGH | MEDIUM | LOW",
  "suggested_title": "Damaged road surface with pothole",
  "suggested_description": "A visible pothole is present on the roadway…",
  "severity": "LOW | MEDIUM | HIGH | UNKNOWN",
  "observations": ["Pothole roughly spans half a lane", "Standing water inside"],
  "uncertainties": ["Depth cannot be judged from the photo"],
  "warnings": ["Faces or licence plates may be visible"]
}
```
Rules in the prompt: describe only what is visible; no location guesses; rate severity conservatively ("potentially"); return `is_civic_issue=false` rather than forcing a category.

### Agent 2 — Department Identification ✅ (M4): **deterministic, not an LLM** `modules/authorities/matcher.py`
`match_authorities(authorities, category=, city=, state=, country=)` is a pure function (no database), so every rule has a plain unit test:
1. Keep `active` departments whose `supported_categories` contain the category and whose country agrees.
2. Score: same city **10**; state-level department of the same state **5**; national **2**; a department in a *different* city is dropped. **+1** if it has an email (a contact the citizen can actually use).
3. Return ranked matches, each with readable `reasons` ("Handles road pothole issues.", "Covers Demo City, where the problem is."), and a `confidence`: `EXACT` = exactly one best match at city level; `PARTIAL` = a tie, or only state/national matches; `NONE` = nothing.

Only `EXACT` is pre-selected in the UI. For `PARTIAL` the citizen must choose; the backend accepts any active department that handles the category and has an email.

No AI produces names, emails, or phone numbers. It's called an "agent" for the five-part story, but its rules are code you can read and test.

### Agent 3 — Complaint Generation ✅ (built in M3) `complaint_writer_agent.py`, prompt `complaint_letter.v1`
The model writes only `subject`, `issue_summary`, `requested_action`. `letter_template.py` builds the letter around them with the facts from the database (reference, type, location, coordinates, observed time, severity, photo count, signature), so facts can't be invented or altered. `template_prose()` is the no-AI fallback.

Input: **confirmed** fields only (title, description, category, severity, address, observed_at, authority name, evidence count, citizen name if privacy settings allow). Output `ComplaintDraft {subject, body, requested_action}`, plain text. Has a `language` parameter (default `en`) for multilingual drafts later. The prompt forbids adding facts that aren't in the input.

### Agent 4 — Monitoring ✅ (M5) `modules/ai/agents/monitoring_agent.py`, prompts `reply_classification.v1`, `followup_letter.v1`
- `classify_reply` → `ReplyClassification {kind, confidence (HIGH/MEDIUM/LOW), reference_number, summary}`. The reply sits inside `<reply>` tags (`<` escaped); the prompt says it is data, never instructions; the summary is sanitised (no links, emails, HTML).
- `write_followup_prose` → `FollowupProse {opening, requested_action}`. The facts in a reminder (our reference, the department's reference, issue, place, submission date, previous reminder date, listed response time) come from `followup_template.py`, never from the model. If the AI fails, the template wording is used.

**Backend rules (`monitoring/rules.py`), not the model, decide what happens.** The AI's reading is applied only if its confidence isn't `LOW`; otherwise (or if the AI is down or returns invalid output) the reply waits for the citizen to choose its meaning, and the same rules then apply.

| Meaning | Status change (if the status machine allows it) | Reminders |
|---|---|---|
| `ACKNOWLEDGMENT` | → `ACKNOWLEDGED` (never backwards) | stop; new check later (`PROGRESS_REPLY`) |
| `IN_PROGRESS` | → `IN_PROGRESS` | stop; new check later |
| `RESOLVED_CLAIM` | → `RESOLVED_PENDING_VERIFICATION` (still needs the citizen) | stop for good |
| `REQUEST_FOR_INFO` | none | stop: the citizen replies to the department |
| `REJECTION` | none | stop; **escalation recommended** |
| `UNRELATED` | none | unchanged (an auto-reply doesn't count as an answer) |

The worst a malicious reply can do is move a case to "awaiting your verification" (and stop reminders), and that state needs the citizen. A reply can never close, verify, cancel or send anything (tested for every kind × every status).

**Reference numbers:** only a value with a safe format (letters, digits, `/`, `-`, at least one digit, 4–40 chars) that appears **word-for-word** in the reply, and isn't CivicPulse's own reference, is kept. A deterministic extractor finds it even without AI. It's copied onto the complaint only from a reply about this complaint (not `UNRELATED`).

### Agent 5 — Resolution Verification ✅ (M6) `modules/ai/agents/resolution_agent.py`, prompt `resolution.v1`
Input: the original ("before") photo and a follow-up ("after") photo, each labelled, both EXIF-free and resized by `image_prep`. Output `ResolutionAssessment {assessment: APPEARS_RESOLVED | PARTIALLY_RESOLVED | NOT_RESOLVED | CANNOT_DETERMINE, confidence, same_location_likely: YES | NO | UNSURE, visible_changes[], remaining_problems[], uncertainties[], summary}`, all strings sanitised. The prompt says a photo can't prove a repair ("appears", never "definitely"), prefers `CANNOT_DETERMINE` for different places or angles, and treats any text in the photos (e.g. a sign saying "repaired") as part of the scene, never as evidence or instructions.

**The citizen decides; rules check the decision** (`resolutions/rules.py`, pure functions):
- `cautions(assessment)`: plain warnings for a different or uncertain place, `CANNOT_DETERMINE`, partial or not resolved, low confidence, or no AI at all; always "The AI can be wrong. Only your own check decides."
- `transitions_for(decision, status)`: confirm from `RESOLVED_PENDING_VERIFICATION` → `VERIFIED_RESOLVED`, or from a waiting status via `RESOLVED_PENDING_VERIFICATION` (a fix the citizen found first); dispute only from `RESOLVED_PENDING_VERIFICATION` → `REOPENED`. Every path is checked against the status machine in a test.
- The citizen may disagree with the AI either way. A decision needs `checked_myself: true`.

**Reopening:** disputing a claimed repair, or reopening a verified/closed complaint, sets `REOPENED` (a waiting status, so monitoring applies again) and drafts a "not fixed" message from a template (with the citizen's note). It is only sent after approval, and it doesn't use up the reminder limit. If the department stays silent afterwards, reminders start again at number 1.

### Prompt-injection safeguards (all agents) — implemented in M3
- Free-text outputs pass through `modules/ai/sanitize.py` (links, emails, HTML/markdown tags, control characters removed; lengths capped), unknown output fields are dropped (so no smuggled `location`), and a test simulates a model echoing injected text.
- Untrusted content (email bodies, text visible in photos) sits inside clearly delimited blocks. The system prompt says that content is data and never instructions.
- Outputs are schema-constrained (enums, max lengths). The backend re-validates them.
- AI outputs **never** choose recipients, send messages, or skip approval.
- Inbound email is converted to plain text, length-limited, and rendered as text (React escapes it). It is never rendered as HTML.

## 5. Follow-up & escalation rules ✅ (M5)

Settings: `FOLLOWUP_FIRST_AFTER_DAYS=7`, `FOLLOWUP_INTERVAL_DAYS=7`, `FOLLOWUP_MAX_COUNT=2`, `SCHEDULER_MAX_ATTEMPTS=3`.

**Policy-aware deadlines** (`rules.next_check`):
- After the complaint is sent: the **response time listed for the department** (`authorities.service_timeline_days`), else `FOLLOWUP_FIRST_AFTER_DAYS`. The page says which one it used.
- After a reminder is sent, or the citizen chose not to send one: `FOLLOWUP_INTERVAL_DAYS`.
- After "received"/"in progress" and then silence: the later of the department's own deadline and one interval after its last update.

**The cycle:**
1. Every sent message (complaint or reminder) schedules one `FOLLOWUP_CHECK`, key `followup_check:<complaint>:after:<message>`.
2. When it's due, the worker **re-checks everything at run time** and skips (`SKIPPED`, with the reason) if: the complaint is no longer waiting (`SUBMITTED`/`ACKNOWLEDGED`/`IN_PROGRESS`/`REOPENED`); a reply came in after that message; a reply waits for the citizen's review; or a reminder is already waiting.
3. Otherwise, if fewer than `FOLLOWUP_MAX_COUNT` reminders were sent: it **drafts** reminder *n* (`FOLLOW_UP`, `DRAFT`) and records `FOLLOWUP_SUGGESTED`. **Nothing is sent.**
4. The citizen edits, approves (content hash) and sends it, or dismisses it (a new check one interval later).
5. With the maximum already sent: `ESCALATION_RECOMMENDED` (once), listing the department's higher offices from the directory (active, with an email or phone). If there are none, it says so: contacts are never guessed. Nobody is contacted for the citizen.

**Stopping (cancellation):** pending checks and unsent reminders are cancelled (`FOLLOWUPS_STOPPED`) when the department replies (acknowledged, in progress, fixed, asks for information, declines), and when the citizen **withdraws** (cancels) or closes the complaint. Sending re-checks the rules, so a cancelled or out-of-date reminder can't go out.

**Worker reliability:** actions are claimed one at a time with `SELECT … FOR UPDATE SKIP LOCKED` (two workers never run the same one); a failure is retried with back-off (5, 10, 20 min) and becomes `FAILED` after `SCHEDULER_MAX_ATTEMPTS`; a run left `RUNNING` for 15 minutes (crashed worker) is picked up again; one broken action never stops the others.

### Duplicate-send prevention (defence in depth)
1. ✅ `scheduled_actions.idempotency_key` is UNIQUE (one check per message), so the same check can't be scheduled twice; a reminder's key is `followup:<action_id>`, so one check can never create two drafts.
2. ✅ The worker claims rows with `SELECT … FOR UPDATE SKIP LOCKED`, so two workers never run the same action.
3. ✅ `send` locks the message row (`SELECT … FOR UPDATE`) and moves `APPROVED → SENDING` (committed) before calling the provider, so a second call waits, then sees `SENDING`/`SENT` and gets `409` or the existing result. A `SENDING` row older than 10 minutes counts as stuck and may be retried.
4. ✅ `communications.idempotency_key` (`complaint:<id>:v<n>`) is UNIQUE and also goes to the provider, which returns its earlier result for a repeated key.
5. ✅ Approval stores a SHA-256 of recipient + subject + body + attachments. The client sends the hash of the preview it showed; a mismatch is `409`. Editing the complaint, re-drafting the letter, or changing the department withdraws the approval (`APPROVAL_WITHDRAWN`, back to `DRAFT`) and marks the old message `SUPERSEDED`, so it can never be sent.

### Real-send safety guard (M4)
Only the mock provider exists, and it never contacts anyone (`is_simulated = true`, status `SIMULATED_SENT`). For any future real provider, `send` additionally refuses (`403 REAL_SUBMISSION_BLOCKED`) unless `ALLOW_REAL_SUBMISSIONS=true` **and** the department is a non-demo record with a non-reserved email domain. The database forbids `SENT` on a simulated row.

### Demo time-travel
`python -m app.workers.run_pending --now 2026-12-01T10:00:00Z` runs the worker as if it were that date (only with `ENABLE_SIMULATION=true`). `--now` only decides which checks are due; everything is still recorded with the real time. In the UI, *Demo tools → Skip ahead to the next check* does the same for one complaint (`POST /complaints/{id}/simulation/advance`).

## 6. Semester demo journey (automated in Playwright: `e2e/complaints.spec.ts`, `monitoring.spec.ts`, `resolution.spec.ts`)

1. Register → empty dashboard.
2. Report: upload a pothole photo → (mock or real) AI suggests "Road Pothole" → edit the title → enter an address in *Demo City* → the demo Roads and Infrastructure Department is matched → generate the complaint → edit → approve → **simulated** send.
3. Details page: timeline shows each step; communication shows "Simulated".
4. Simulate reply "acknowledgment with reference CP-REF-1234" → status `ACKNOWLEDGED`, reference stored.
5. *Skip ahead to the next check* (or the worker with `--now` +8 days) → reminder suggested → approve → simulated send. ✅ automated in `e2e/monitoring.spec.ts`.
6. Simulate reply "work completed" → `RESOLVED_PENDING_VERIFICATION`.
7. Upload an "after" photo → AI assessment → the citizen **disputes** → `REOPENED` → approve and send the "not fixed" message. Simulate another completion → upload → confirm → `VERIFIED_RESOLVED`; the history shows both checks. ✅ automated in `e2e/resolution.spec.ts`.
8. Bonus: simulate the prompt-injection reply. With the demo AI it is read as "says it's resolved" (it contains that word): the worst possible effect, which still needs the citizen's photo check; nothing is closed or sent.
