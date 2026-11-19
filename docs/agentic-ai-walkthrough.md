# CivicPulse AI walkthrough for the presentation and viva

## The project in 60 seconds

CivicPulse helps a citizen report a public infrastructure issue and follow it through to a verified repair. Four AI agents handle five bounded tasks. The Vision agent interprets a photo. The Complaint Writer drafts wording. The Monitoring agent classifies replies and drafts reminders. The Resolution agent compares before and after photos. FastAPI orchestrates those tasks based on user actions, incoming replies and scheduled checks. PostgreSQL stores the complaint, evidence metadata, AI outputs, communications and timeline. The citizen confirms the location, approves outgoing messages and decides whether the repair is complete.

The app supports a deterministic mock provider, local Ollama inference with pretrained Gemma 3, and pretrained Claude through the Anthropic API. The project team wrote the prompts, output schemas and workflow rules. There was no custom training or fine-tuning, and there is no benchmark of model accuracy yet.

## The full journey

| What the audience sees | What runs internally |
|---|---|
| The citizen signs in and starts a report | FastAPI creates a server-side session and saves a complaint in `DRAFT`. Each complaint gets a public reference. Ownership is checked before granting access to a complaint or its photos. |
| The citizen attaches a photo | The evidence service decodes and validates the upload, strips embedded metadata such as EXIF/GPS, stores the cleaned bytes privately and saves an `ORIGINAL` evidence record. |
| AI suggests report details | The Details step checks for a prior result for that photo and requests Vision analysis when needed. Suggestions fill empty fields or appear as alternatives when the citizen has already typed something. The citizen saves the details. |
| The citizen confirms the address | The citizen enters or selects an address and confirms it. The location search can help with this step. The image analysis carries no location field. |
| The app suggests a department | Backend code filters active directory entries by category and jurisdiction, then ranks city above state and national coverage. The citizen confirms the selection. The demo can explicitly offer fictional departments when no local match exists. |
| A formal letter appears | The Complaint Writer returns wording. A backend template inserts saved facts and the citizen reviews the completed draft. |
| The citizen approves and sends | The preview provides a SHA-256 fingerprint of the recipient, subject, body and attachment IDs. Approval binds the message to those exact values. An edit invalidates approval. The backend checks the hash, uses a row lock and idempotency key, and records `SIMULATED_SENT`. The complaint becomes `SUBMITTED`. |
| A reply or a deadline arrives | A reply triggers classification. An expired deadline can trigger a reminder draft. The workflow evaluates saved state before either result can affect the complaint. |
| The department claims a repair | The backend can move the case to `RESOLVED_PENDING_VERIFICATION`. The citizen supplies an after photo, reviews the comparison and confirms or disputes the repair. |

The timeline is backed by `complaint_events`. The dashboard and notification bell read saved events and workflow state. Refreshing the browser does not erase progress. [Architecture](architecture.md), [database tables](database.md), [state machine](../backend/app/modules/complaints/status_machine.py), [approval and sending](../backend/app/modules/communications/service.py).

## How a model call works

1. A React action calls a same-origin `/api/v1/…` endpoint through the shared API client. Next.js forwards it to FastAPI. For background work, the worker calls the service layer directly.
2. FastAPI checks session and ownership for user requests, then the service loads the data needed for the current task. The Python agent function supplies the versioned prompt, input parts and expected Pydantic output schema to `AIProvider.generate_structured()`.
3. The provider factory selects mock or Anthropic on the server. The Anthropic adapter converts each `ImagePart` to a Base64 image block and sends it with the text to `client.beta.messages.parse()`. The decoder returns a structured answer shaped by the Pydantic model. Output text is sanitised and enumerated values are restricted to allowed choices.
4. The service records model results or provider failures in `ai_analyses`, including the provider, prompt version and mock flag. It then returns suggestions, renders a draft or applies a narrowly defined workflow rule. Retry and manual paths depend on the task.

The Python agent functions are prompts plus typed input/output contracts. A single configured provider serves all four. Workflow routing lives in application code, so each action has a defined trigger and an auditable effect. [Provider factory and adapter](../backend/app/integrations/ai_providers), [analysis schemas](../backend/app/modules/ai/schemas.py), [audit service](../backend/app/modules/ai/service.py).

## 1. Vision agent

**Trigger.** After an original photo is saved, the Details screen automatically requests analysis once if the current photo has no matching result. It reads the latest successful result with `GET /api/v1/complaints/{id}/analysis` and can start a call with `POST /api/v1/complaints/{id}/analysis` with the photo's `evidence_id`. The service requires an owned, editable complaint and selects the requested original photo, or the first original when no ID was supplied.

**How detection works.** The backend opens the stored image with Pillow, converts it to RGB, scales the longest edge to at most 1,568 pixels while keeping the aspect ratio and encodes JPEG. The agent passes the image and `vision.v1` to the provider. With Claude enabled, the pretrained multimodal model interprets visual features in the image and selects among the prompt's categories, including potholes, broken streetlights, garbage, drains, leaks, waterlogging and other damage. CivicPulse supplies category definitions and asks for visible evidence and uncertainties. It expects a scene-level classification and description. The app implements no bounding-box detector, pixel segmentation or custom computer-vision model.

**Output and effect.** `VisionAnalysis` contains the civic-issue flag, category, confidence, suggested title and description, severity, observations, uncertainties and warnings. For example, damaged road surface can support `ROAD_POTHOLE`; depth can remain unknown. The prompt asks for conservative severity and `OTHER` with `UNKNOWN` severity when a civic problem is unclear. Confidence labels are qualitative. The service saves the analysis and a timeline event. The user can edit the returned suggestions or complete the report manually after a failure.

**What the demo actually does.** With `AI_PROVIDER=ollama`, Gemma receives the prepared image on the laptop and returns a structured analysis. With `AI_PROVIDER=mock` and `MOCK_AI_SCENARIO=pothole`, the provider returns the preset pothole sample and displays the Demo AI badge. [Details screen](../frontend/src/features/complaints/report-wizard/details-step.tsx), [local provider](../backend/app/integrations/ai_providers/ollama_provider.py), [image preparation](../backend/app/modules/ai/image_prep.py), [agent](../backend/app/modules/ai/agents/vision_agent.py), [prompt](../backend/app/modules/ai/prompts/vision_v1.py).

## 2. Complaint Writer agent

**Trigger.** The Letter step requests a first draft automatically when it opens with no existing draft. `POST /api/v1/complaints/{id}/complaint-draft` accepts `mode: ai` or `mode: template`. The service requires an editable complaint, title, description, category and confirmed location. Replacing an existing draft requires explicit confirmation.

**Input and inference.** The service builds a facts object from saved data, such as public reference, issue, citizen description, address, observation time and photo count. Name and exact coordinates depend on privacy preferences. The agent submits escaped JSON inside a `<facts>` block using `complaint_letter.v1`. Its `ComplaintLetterProse` response contains a subject, issue summary and requested action.

**Output and effect.** The template assembles the final subject and body with a factual section from the database. Recipient selection comes from the directory. The citizen reviews or edits the prose before approving; regeneration withdraws existing approval. If AI drafting fails, the citizen can use a basic template and edit it. [Letter screen](../frontend/src/features/complaints/report-wizard/letter-step.tsx), [agent](../backend/app/modules/ai/agents/complaint_writer_agent.py), [letter assembly](../backend/app/modules/ai/letter_template.py).

## 3. Monitoring agent, task A — classify a reply

**Trigger.** In development, the citizen uses **Demo tools** to simulate a department reply. The UI calls `POST /api/v1/complaints/{id}/simulation/reply`. The simulation passes a sample message to `monitoring.service.receive_reply()`, which stores the inbound communication and calls the classifier. The project has no live mailbox integration.

**Input and inference.** The agent sends the complaint reference and escaped reply subject/body inside delimited input to `reply_classification.v1`. The prompt sees up to 8,000 body characters. `ReplyClassification` returns a reply kind, confidence, optional reference and short summary. The mock uses keyword rules. The backend checks that a candidate reference has a valid format, appears verbatim in the inbound message and differs from CivicPulse's own reference. A deterministic extractor can recover a reference independently.

| Interpretation | Backend effect, when allowed by the current state |
|---|---|
| Acknowledgement | Move forward to `ACKNOWLEDGED` and recalculate the next check. |
| In progress | Move forward to `IN_PROGRESS` and recalculate the next check. |
| Claims repair complete | Move to `RESOLVED_PENDING_VERIFICATION` and stop normal reminders. |
| Requests information | Keep the status and stop reminders so the citizen can respond. |
| Rejection | Keep the status, stop reminders and recommend escalation when applicable. |
| Unrelated | Keep the status and existing monitoring plan. |

The service sends low-confidence, unavailable or invalid classifications to citizen review. Once the citizen chooses a meaning, the same rule function handles it. A model response cannot verify a repair or issue a send command. [Agent](../backend/app/modules/ai/agents/monitoring_agent.py), [reply handling](../backend/app/modules/monitoring/service.py), [reply and deadline rules](../backend/app/modules/monitoring/rules.py).

## 4. Monitoring agent, task B — draft a reminder

**Trigger.** An accepted simulated send creates a `scheduled_actions` check. The first deadline uses the department's listed response time or the configured default, typically seven days. The worker entry point is `python -m app.workers.run_pending`. In the demo, **Skip ahead to the next check** runs the same due-check logic for the complaint. A deployed worker would need an external schedule to execute periodically.

**Rules and inference.** The worker claims due rows with `FOR UPDATE SKIP LOCKED` and rechecks the complaint before drafting. For example, it skips drafting when a relevant reply changed the plan, classification awaits review or a draft already exists. If eligible and below the reminder cap, it builds facts from the complaint and communication history, then calls `followup_letter.v1`. The agent returns only an opening and requested action. The template supplies stored facts such as dates and references. If generation fails, the service substitutes template wording automatically.

**Output and effect.** The worker creates a draft communication and records a timeline event. The citizen edits, approves and sends the reminder, or dismisses it. The default cap is two ordinary sent reminders. A later eligible check at the cap suggests escalation using the directory's contacts. Acknowledgement and progress can reschedule checks. Rejection, information requests and repair claims stop normal reminders. [Worker entry point](../backend/app/workers/run_pending.py), [draft and escalation logic](../backend/app/modules/monitoring/service.py), [reminder template](../backend/app/modules/ai/followup_template.py).

## 5. Resolution agent

**Trigger.** The repair-check UI saves a `FOLLOWUP` photo and requests `POST /api/v1/complaints/{id}/resolution-reviews` with its ID. The backend checks ownership, an eligible complaint status and the photo type. It fetches the first `ORIGINAL` and the chosen `FOLLOWUP` photo. A completed review for the same photo is reused and a failed analysis can be retried.

**How comparison works.** Both photos go through the same image preparation as Vision. `resolution.v1` receives them in one model request with explicit BEFORE and AFTER labels. The prompt asks whether visible landmarks and surroundings appear to match, what changed and what remains. Poor views or an apparent location mismatch should produce uncertainty. The live model would interpret the image pair holistically. The demo returns the configured repair sample and does not compare the pixels.

**Output and effect.** `ResolutionAssessment` includes `APPEARS_RESOLVED`, `PARTIALLY_RESOLVED`, `NOT_RESOLVED` or `CANNOT_DETERMINE`, plus confidence, likely same location, visible changes, remaining problems and uncertainties. The service stores the advice in `resolution_reviews`. If the original photo is missing or AI fails, the citizen can still make a manual decision. Confirming after checking can set `VERIFIED_RESOLVED`. Disputing a repair claim sets `REOPENED` and creates an unsent template notice for review and approval. [Agent](../backend/app/modules/ai/agents/resolution_agent.py), [prompt](../backend/app/modules/ai/prompts/resolution_v1.py), [review and decision service](../backend/app/modules/resolutions/service.py).

## Questions the examiner is likely to ask

**What makes this agentic?** The workflow has persistent state and calls specialised agents at different times in pursuit of a complaint's resolution. A reply or deadline can trigger a task without the citizen drafting a new prompt. Its autonomy is limited to predefined tasks and transitions, with citizen approval for sending and repair verification.

**How do agents communicate?** The workflow passes data through PostgreSQL and service calls. The Vision result is reviewed into saved complaint fields, which the Writer reads. The Monitoring result can make a repair check relevant, which later uses saved photo records. There is no agent-to-agent conversation loop.

**What happens if AI hallucinates or someone puts instructions in a reply?** Prompts frame those inputs as data, enforce a structured response and constrain the model's available outputs. Backend rules verify authority records, reference strings, permitted transitions and approved content. A plausible but incorrect suggestion can still occur, which is why the citizen reviews the result.

**What did we test, and what would a real model evaluation look like?** The verified local run passed 475 backend tests and 119 frontend unit tests. Those test application behavior, including mock integration, workflow rules and fallbacks. For a live evaluation, keep human-labelled examples separate from prompt tuning. Measure per-class precision/recall and macro-F1 for photos and replies, factual consistency of letters, agreement with human repair reviewers, and median latency. Include ambiguous inputs and cases where the expected answer is uncertainty. There are no measured live scores to report yet. [Verification history](progress.md), [mock implementation](../backend/app/integrations/ai_providers/mock_provider.py).

## A live demo you can narrate

For the two-screen version, open the [department inbox](../department/README.md) alongside the citizen app. After the citizen approves and sends to the configured demo department, the inbox raises a new-report alert. The operator can read the approved letter and photos and post a repair update. The citizen app refreshes and asks for verification. A structured operator update goes directly to the backend's reply rules. The separate simulated free-text reply flow still demonstrates the Monitoring agent's classification.

1. Upload a pothole image. Explain the image-to-schema call and which provider is active. Edit the suggested title and confirm the address.
2. Select the directory entry, inspect the generated letter, approve it and send. Show the simulated delivery label.
3. For the cleanest reminder demo, skip ahead before simulating a reply. Show the draft waiting for approval.
4. Simulate an acknowledgement and point out the verbatim department reference. Then simulate a completed repair and show that the case is awaiting the citizen's verification.
5. Upload an after photo, explain the comparison fields and choose **Not fixed** if you want to demonstrate reopening. The new notice is a draft. A later repair check can demonstrate **Verified resolved**.

For a code demonstration, open the Vision agent first, follow `generate_structured()` into the provider and then show the service that stores its output. Each of the other agents follows the same contract. [Detailed API inventory](presentation-technical-inventory.md).
