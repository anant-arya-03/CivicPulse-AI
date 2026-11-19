# CivicPulse AI, explained from the code

## What to say first

> CivicPulse uses four AI agents to help a citizen report an issue and follow it through to a repair check. Our Python backend chooses which agent to call based on the stage of the complaint. Each agent sends a task-specific prompt and input to a pretrained Gemma model running locally through Ollama. The backend validates the model's response and applies fixed workflow rules. The citizen approves outgoing messages and makes the final repair decision.

## The stack and what each part does

| Part | What we use |
|---|---|
| Website | Next.js, React and TypeScript. TanStack Query connects the screens to the backend. |
| Backend | Python and FastAPI. Routers handle HTTP requests and services implement the workflow. |
| Database | PostgreSQL stores complaints, timeline events, messages, scheduled checks and AI results. SQLAlchemy reads and writes those records. Alembic manages schema changes. |
| AI runtime and model | Ollama runs pretrained **Gemma 3 4B** (`gemma3:4b`) locally. Gemma interprets text and images. |
| Model integration | Our own Python `AIProvider` interface, a direct HTTP request to Ollama, and Pydantic to validate the model response. |
| Image preparation | Pillow converts and resizes uploaded photos before model inference. |

**Did we use LangChain or LangGraph?** No. Our workflow is written directly in Python. FastAPI services, a complaint state machine and a scheduled worker decide which step runs. Our project includes an Anthropic adapter as an alternative, and a mock provider for repeatable tests. The local demo uses Ollama and needs no Anthropic key. [Backend dependencies](backend/pyproject.toml) · [Frontend dependencies](frontend/package.json)

## Where the LLM is actually called

```text
Browser or scheduled worker
  → FastAPI router / Python service
  → agent function selects prompt, input and output schema
  → provider.generate_structured(...)
  → POST http://127.0.0.1:11434/api/chat
  → Ollama runs Gemma
  → backend validates the JSON and records the result
  → UI suggestion or backend workflow rule
```

1. The root `.env` selects `AI_PROVIDER=ollama` and `OLLAMA_MODEL=gemma3:4b`. [`factory.py → get_ai_provider()`](backend/app/integrations/ai_providers/factory.py#L11) creates the provider.
2. Each agent calls `provider.generate_structured()` with its prompt, input and expected Pydantic class. That is the **agent's call to the provider**.
3. [`ollama_provider.py:50`](backend/app/integrations/ai_providers/ollama_provider.py#L50) builds the request to Ollama. [Line 68](backend/app/integrations/ai_providers/ollama_provider.py#L68) sends it. The request includes the model name, messages, Base64-encoded images when applicable, and the JSON schema in `format`.
4. Ollama returns JSON text in `message.content`. [Line 84](backend/app/integrations/ai_providers/ollama_provider.py#L84) uses `model_validate_json()` to check it. For example, an invented category outside the allowed enum fails validation. A valid category can still be wrong about the photo.
5. [`ai/service.py`](backend/app/modules/ai/service.py#L87) records successful outputs or provider failures in `ai_analyses`. The caller uses the result according to the rules of that task.

## Follow one request in your IDE

### 1. Vision agent — understand the uploaded photo

- **Trigger.** When you reach the Details step with an uploaded photo that needs analysis, [`details-step.tsx`](frontend/src/features/complaints/report-wizard/details-step.tsx#L85) calls `runAnalysis(photo.id)`. The mutation sends `POST /api/v1/complaints/{id}/analysis` with the evidence ID. Uploading the photo and analysing it are separate requests.
- **Backend path.** [`ai/router.py → analyze_photo()`](backend/app/modules/ai/router.py#L36) calls [`ai/service.py → analyze_photo()`](backend/app/modules/ai/service.py#L159). The service checks that the citizen owns an editable complaint, reads its original photo from private storage, and calls [`prepare_for_model()`](backend/app/modules/ai/image_prep.py#L16) to make an RGB JPEG with a longest edge of at most 1,568 pixels.
- **Agent code.** [`vision_agent.py → analyze_photo()`](backend/app/modules/ai/agents/vision_agent.py#L11) sends the prepared image and [`vision.v1` prompt](backend/app/modules/ai/prompts/vision_v1.py) to the provider. The prompt defines categories such as potholes, broken streetlights and open drains and asks for visible observations and uncertainty.
- **What detection means.** Gemma uses its pretrained visual understanding to interpret the scene and suggest a category. CivicPulse does scene classification and description, with no custom bounding-box detector or training pipeline. A break in the road surface can support a pothole suggestion, while the depth may remain unknown.
- **Output.** [`VisionAnalysis`](backend/app/modules/ai/schemas.py#L38) includes the category, suggested title and description, severity, confidence and observations. The UI lets the citizen edit the suggestions. The citizen enters the location separately. If AI is unavailable, the citizen fills in the form.

### 2. Complaint Writer — draft the letter

- **Trigger.** The [Letter step](frontend/src/features/complaints/report-wizard/letter-step.tsx#L60) asks for a draft if one does not exist. `POST /api/v1/complaints/{id}/complaint-draft` calls [`generate_complaint_draft()`](backend/app/modules/ai/service.py#L220).
- **Agent code.** [`complaint_writer_agent.py → write_letter_prose()`](backend/app/modules/ai/agents/complaint_writer_agent.py#L14) sends stored facts to Gemma with `complaint_letter.v1`. The schema requires a subject, issue summary and requested action.
- **After the call.** [`render_letter()`](backend/app/modules/ai/letter_template.py#L99) combines the proposed wording with saved facts. The citizen edits or approves the finished draft. A standard template is available if model generation fails. The recipient comes from a deterministic directory match. The [sending service](backend/app/modules/communications/service.py#L290) checks the exact approved content before recording a simulated send.

### 3. Monitoring agent — read replies and draft reminders

- **When a free-text reply arrives.** [`monitoring/service.py → receive_reply()`](backend/app/modules/monitoring/service.py#L223) saves the reply, then [`ai/service.py → classify_reply()`](backend/app/modules/ai/service.py#L298) calls [`monitoring_agent.py → classify_reply()`](backend/app/modules/ai/agents/monitoring_agent.py#L22). The model returns the reply kind, confidence, summary and possible reference number. The backend checks that any accepted reference appears verbatim. Fixed [reply rules](backend/app/modules/monitoring/rules.py) decide the status effect. Low confidence or failure leaves the meaning for the citizen to review.
- **When a deadline expires.** The [worker](backend/app/workers/run_pending.py#L33) calls `run_due_actions()`. [`_run_followup_check()`](backend/app/modules/monitoring/service.py#L533) checks whether the complaint is still waiting and eligible for a reminder. If eligible, [`monitoring_agent.py → write_followup_prose()`](backend/app/modules/ai/agents/monitoring_agent.py#L39) generates an opening and requested action. The backend adds saved facts, creates a draft and waits for citizen approval. A template supplies wording if the model fails.

### 4. Resolution agent — compare before and after

- **Trigger.** The [repair-check hook](frontend/src/features/complaints/hooks.ts#L360) uploads a new photo and requests `POST /api/v1/complaints/{id}/resolution-reviews`. [`resolutions/service.py → create_review()`](backend/app/modules/resolutions/service.py#L114) validates access and picks the original and follow-up images.
- **Agent code.** [`ai/service.py → compare_photos()`](backend/app/modules/ai/service.py#L356) prepares both images. [`resolution_agent.py → compare_photos()`](backend/app/modules/ai/agents/resolution_agent.py#L11) sends both in order with BEFORE and AFTER labels. The model reports visible changes, whether the scene appears to match, and an assessment such as `CANNOT_DETERMINE`.
- **After the call.** The backend stores the assessment as advice. [`decide()`](backend/app/modules/resolutions/service.py#L195) separately handles the citizen's confirmation or dispute. A repair claim by itself only reaches `RESOLVED_PENDING_VERIFICATION`.

## Viva answers

| Question | Answer you can give |
|---|---|
| What makes the project agentic? | The system keeps complaint state and invokes specialised tasks when a photo, reply, deadline or repair check calls for one. The backend controls the permitted actions. |
| Are there four different models? | One configured model is shared. There are four agent modules and five tasks because Monitoring does both classification and reminder drafting. |
| How do the agents know what happened previously? | Services load the relevant records from PostgreSQL and pass the necessary context into each request. The model is called independently for each task. |
| Did we train the model or use RAG? | We use a pretrained model with custom prompts and schemas. There was no fine-tuning, embedding search or vector database. Services pass relevant stored facts directly. |
| Can the model send a message or verify a repair? | Sending requires approval of the exact message. Final repair verification requires the citizen's decision. The model generates suggestions and drafts. |
| What if the model returns wrong or invalid JSON? | Pydantic validates the response format. The workflow handles failures with manual paths or templates. Correct JSON can still contain factual mistakes, so review matters. |
| What results can we present? | The verified app suites had **481 backend** and **119 frontend** tests passing. In a small Ollama smoke run, **6 of 6 calls** returned schema-valid output. Vision took about **91.5 s on the first call** and **13.6 s on the next call** on the local laptop. These are app checks and individual response timings. Model accuracy and F1 require a labelled benchmark. |

**Best order for a code demo.** Open `vision_agent.py` first, jump to `ollama_provider.py:68` to show the real model call, then open `ai/service.py:159` to show what happens before and after inference. Use the Monitoring deadline example to explain how the workflow calls an agent even when the citizen is away. [Detailed test and metrics notes](docs/backend-agent-implementation-and-metrics.md)
