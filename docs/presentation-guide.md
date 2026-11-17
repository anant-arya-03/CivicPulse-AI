# CivicPulse AI — easy project guide

Updated **17 November 2026**. Start here; open the linked references only when you need more detail.

> **AI suggests → backend rules decide → the citizen approves.**

## 1. What it does

CivicPulse helps a citizen report a public infrastructure problem, prepare a formal complaint, track replies and reminders, and verify a repair. The current product is a working **simulation**: accounts, storage, approvals and workflow rules execute normally, while AI/email use controlled mock providers and departments are fictional.

**Journey:** Photo → review details → confirm location → choose department → review letter → approve simulated send → track → verify or dispute.

## 2. Technology: what each part does

| Part | Technology | Job | Evidence |
|---|---|---|---|
| Website | Next.js 16.4.6, React 19.3, TypeScript 5 | Pages, interaction and type checks | [Frontend packages](../frontend/package.json) |
| UI/forms | Tailwind 4, shadcn/Radix, React Hook Form, Zod | Styling, controls and input validation | [Features](../frontend/src/features), [theme](../frontend/src/app/globals.css) |
| Browser data/maps | TanStack Query, Leaflet | Fetch/cache API data and display location | [Hooks](../frontend/src/features/complaints/hooks.ts), [map loader](../frontend/src/components/complaints/location-map-loader.tsx) |
| Backend | Python 3.11+, FastAPI, Pydantic, Uvicorn | HTTP API, validation and business rules | [Dependencies](../backend/pyproject.toml), [app](../backend/app/main.py) |
| Database | PostgreSQL 17, sync SQLAlchemy 2.1, psycopg 3, Alembic | Persistent records, transactions and migrations | [Models](../backend/app/models.py), [migrations](../backend/alembic/versions) |
| AI/images | MockAIProvider / Anthropic adapter, Pillow | Structured suggestions and image processing | [Providers](../backend/app/integrations/ai_providers), [validation](../backend/app/modules/evidence/image_validation.py) |
| Quality | Pytest, Vitest, Playwright, axe-core, Ruff, ESLint | Rules, components, journeys, accessibility and lint | [Verification record](progress.md#current-verification) |

Architecture: **browser → Next.js → FastAPI services → PostgreSQL/private files/provider interfaces**. A separately invoked Python worker processes scheduled checks. This is a modular monolith, with no LangGraph, vector database or custom model-training pipeline. [Architecture details](architecture.md).

## 3. How each feature works — with evidence

| Feature | What happens | Code / test evidence |
|---|---|---|
| Login and ownership | Password is Argon2-hashed; server sessions identify users; other users' resources return 404. | [Security](../backend/app/core/security.py), [auth tests](../backend/tests/test_auth.py) |
| Photo upload | Decode real JPEG/PNG/WebP, enforce limits, strip EXIF/GPS, store private bytes and metadata. | [Image validation](../backend/app/modules/evidence/image_validation.py), [evidence tests](../backend/tests/test_evidence.py) |
| Details and location | Citizen reviews suggestions and explicitly confirms the address. Existing input is preserved. | [Suggestion rules](../frontend/src/features/complaints/ai-suggestions.ts), [tests](../frontend/src/features/complaints/ai-suggestions.test.ts) |
| Department | Fixed category/location scoring over directory records; citizen confirms. No invented contacts. | [Matcher](../backend/app/modules/authorities/matcher.py), [matcher tests](../backend/tests/test_authority_matcher.py) |
| Noida demo choice | No local match is expected. Explicitly choose a fictional demo department; keep the entered address. | [Department step](../frontend/src/features/complaints/report-wizard/department-step.tsx), [browser journey](../frontend/e2e/department-demo.spec.ts) |
| Letter | AI supplies wording; template inserts stored facts. User edits or uses the manual template. | [Template](../backend/app/modules/ai/letter_template.py), [AI API tests](../backend/tests/test_ai_api.py) |
| Approval/send | Hash binds approval to recipient, subject, body and attachment IDs; edits withdraw it; idempotent send prevents repeat effects. | [Hash](../backend/app/modules/communications/hashing.py), [submission tests](../backend/tests/test_submission.py) |
| Replies/reminders | Reply meaning feeds fixed status rules; due checks draft reminders, never auto-send. Current limit: two ordinary reminders, then escalation advice. | [Rules](../backend/app/modules/monitoring/rules.py), [worker tests](../backend/tests/test_monitoring.py) |
| Repair decision | Compare before/after as advice; citizen confirms or disputes. Dispute reopens and creates an unsent notice. | [Resolution service](../backend/app/modules/resolutions/service.py), [tests](../backend/tests/test_resolutions.py) |
| Bell/settings | Poll event feed every 30 seconds; sequence cursor tracks seen events. Save preferences; password change revokes sessions. | [Notifications](../backend/app/modules/notifications/service.py), [settings/security tests](../backend/tests/test_polish.py) |

## 4. Four agents, five AI tasks

| Agent | Input → output | Boundary |
|---|---|---|
| Vision | Photo → category, title, description, cautious severity, uncertainty | Cannot infer the address or submit a report. |
| Complaint Writer | Saved facts → subject, summary and requested action | Cannot choose a recipient or approve sending. |
| Monitoring | Reply → meaning; follow-up facts → reminder wording | Cannot verify a repair or send messages. |
| Resolution | Before/after → possible changes and repair assessment | Citizen makes the final decision. |

Monitoring performs two tasks, hence five analysis types across four modules. Department matching is deterministic code, not a fifth AI agent. Agents return constrained Pydantic outputs; services record outcomes in `ai_analyses`. [Agent code](../backend/app/modules/ai/agents), [schemas](../backend/app/modules/ai/schemas.py), [workflow rules](workflows.md).

**Mock limitation:** the active mock does not inspect photos; it returns configured samples and uses keywords for replies. The Anthropic adapter exists, but live model accuracy/access remain unverified. Confidence labels are not measured accuracy percentages.

## 5. Data and safeguards

Ten application tables store users, sessions, complaints, events, evidence, AI analyses, authorities, communications, scheduled actions and resolution reviews. Photo bytes stay in private storage. [Database explanation](database.md); [exact columns, 47 API operations and state transitions](presentation-technical-inventory.md).

- A complaint's `SUBMITTED` state and its message's `SIMULATED_SENT` delivery state are separate. No real email is delivered.
- SHA-256 fingerprints approved content; it is not encryption. CSRF uses a session-bound HMAC token.
- A repair reply can reach only `RESOLVED_PENDING_VERIFICATION`; the citizen alone establishes `VERIFIED_RESOLVED`.
- Privacy preferences affect newly generated letters, not stored locations or existing messages.
- Untrusted replies/photos are data. Constrained outputs and fixed rules limit effects; manual paths remain available.

## 6. Presentation: click and explain

1. **Report:** upload the before photo and review details. Explain the mock AI label.
2. **Location/department:** confirm the address; use the explicit demo choice for Noida.
3. **Letter/send:** inspect recipient and text, approve, then show simulated delivery.
4. **Reminder:** skip ahead; show that only a draft appears. Review and approve it yourself.
5. **Reply:** simulate acknowledgement/progress; show status and reference in the timeline.
6. **Repair:** simulate a fix claim, upload a different after photo, then confirm or dispute after checking it.
7. **Settings/bell:** show persistent preferences and unread events.

For escalation, use a separate unanswered complaint: send reminder 1 and 2 with approval, then advance to the next check. For the main story, an acknowledgement changes the schedule. [Run/setup instructions](development.md), [deployment boundaries](deployment.md).

## 7. Evidence and remaining work

| Evidence | Scope |
|---|---|
| **119 Vitest tests passed** | Rerun during this documentation refresh. |
| **5 backend polish tests passed** | Rerun for settings, session revocation, notification ownership/cursor, privacy and delimiter escaping. |
| **22 browser cases listed** | Inventory confirmed; listing does not execute them. |
| Earlier full backend: **475 passed** | Recorded implementation verification, not rerun in this refresh. |
| Earlier browser: **20 passed + 2 targeted Noida cases passed** | Separate recorded runs; not one new combined 22-case run. |

See [dated verification](progress.md#current-verification). Source/test links show where behaviour is implemented and checked; they do not prove real-world AI accuracy or guarantee zero defects.

**Still needed for real service:** verified official contacts, real outbound/inbound email integration, live AI evaluation, production hosting/backups/scheduling, shared rate limiting and manual screen-reader/security validation. Current delivery, replies and directory remain simulated.

## 8. Where to look next

| Question | Reference |
|---|---|
| How is the code organized? | [Architecture](architecture.md) |
| How do I run, test or troubleshoot it? | [Development](development.md) |
| What does each endpoint accept? | [API](api.md) and local `http://localhost:8000/docs` |
| What is stored, and how are tables related? | [Database](database.md) |
| Which state changes and agent effects are allowed? | [Workflows](workflows.md) |
| What is the UI design and accessibility approach? | [Design system](design-system.md) |
| What has been verified, and what is unfinished? | [Progress](progress.md), [deployment](deployment.md) |