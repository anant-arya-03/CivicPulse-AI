# Patient-message inbox agent

A teaching prototype for the AI in Healthcare capstone. One synthetic portal message becomes a proposed staff routing, a draft reply and, when appropriate, a calendar change. A named reviewer can accept or reject each item. The calendar, outbox and staff queues change only after review. Use the supplied fictional records for demonstrations.

## Set up

Tested with Python 3.13.11 and local Ollama. From the CivicPulse-AI repository root on Linux or macOS, run

```bash
cd patient-message-inbox-agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python score.py --baseline-only
```

The tests use a scripted model and temporary SQLite databases. They run offline after package installation. The starter baseline scores 27/40 on the development set.

For the evaluated route, start Ollama, install the model, and set the model identifier in this shell.

```bash
ollama pull qwen2.5:7b
export AGENT_MODEL=ollama:qwen2.5:7b
```

Alternatively, copy `.env.example` to `.env` and select a provider and tool-capable model. The included provider adapters support Ollama and Google GenAI. For another LangChain provider, install its adapter and configure its provider-specific credentials. An exported `AGENT_MODEL` takes precedence over the local file. Only the Ollama route was evaluated. Check a hosted provider's data terms before submitting synthetic fixtures.

## Open the staff inbox in a browser

After setup, start the local web app from the `patient-message-inbox-agent` directory.

```bash
python -m clinic_inbox.web
```

Open **[Clinicdesk on localhost](http://127.0.0.1:8765)**. A single Python process serves the frontend and the SQLite-backed API. The first launch creates a separate synthetic database named `staff-demo.db` with 40 messages and prepares one urgent example. You can review that example immediately, even without a model. For the other unprocessed messages, start Ollama with `qwen2.5:7b` installed, or set `AGENT_MODEL` to a configured provider.

1. Choose a message in the queue. Search by patient name, message ID or wording. The three count cards filter the queue.
2. For an unprocessed message, select **Prepare proposals**. For a pending review, read the message, flags and appointment times, then choose **Approve** or **Reject** on each item.
3. Enter your reviewer name and select **Save review**. The review record shows which actions applied, which were rejected, and any calendar conflicts. Use **Show → Reviewed** to revisit earlier decisions.
4. Use **Needs attention** for preparation failures. A temporary model connection failure offers **Retry preparation** after service is restored. Other failures show the original message for manual follow-up. **Refresh** reads the latest persisted state.

To open an existing course database, run `python -m clinic_inbox.web --db clinic.db`. Use `--port 8766` if the default port is occupied. Stop the server with Ctrl+C. Restarting with the same database preserves reviews. This interface binds to loopback for use on one workstation with synthetic teaching data.

## Run and review

```bash
python reset_db.py --db clinic.db --messages data/messages_dev.json
python -m clinic_inbox run --db clinic.db --out results.jsonl
python score.py results.jsonl --show
python -m clinic_inbox review --db clinic.db --reviewer staff-01
```

`reset_db.py` replaces the named database and its checkpoints. Use a separate file for each experiment. `run` selects new messages, writes one JSONL row per processed message (including errors), and replaces the specified results file. Use a fresh filename to retain previous outputs. `--ids M001,M011` restricts a run to those IDs. To use the instructor's messages, pass their JSON file to `reset_db.py --messages`.

Review displays urgent proposals first, the original message, each proposed effect and its flags. Enter `a` to approve, `r` to reject or `q` to leave the current message pending. Choices for a message commit together after the last answer. Each audit row identifies the reviewer, decision, flags and outcome. A stale booking or unavailable slot produces a failed calendar item. Rejected routes and error messages need manual follow-up. The outbox is local SQLite storage.

## Two-message viva demonstration

```bash
python reset_db.py --db demo.db
python -m clinic_inbox run --db demo.db --out demo.jsonl --ids M002,M026
python analyze.py --trace demo.db M002
python -m clinic_inbox review --db demo.db --reviewer demo-staff
```

Run the last command in a fresh process. M026 proposes the fixed urgent route and reply with zero model calls. In the recorded local demonstration, M002 proposed cancellation of A02. Approving the route and reply and rejecting that cancellation left A02 booked. Model proposals can vary. Inspect the local decisions with

```bash
python -c "import sqlite3; c=sqlite3.connect('demo.db'); print(c.execute('SELECT proposal_id,reviewer,decision,flags_shown,result FROM audit_log ORDER BY audit_id').fetchall())"
```

## Reproduce the evaluation

The submitted run used `ollama:qwen2.5:7b`, local model ID `845dbda0ea48`, temperature 0, prompt version 2, on 23 November 2026. Five final JSONL files live in `results/`. To recalculate the tables from them **without calling a model**, run

```bash
python analyze.py --results results
python score.py results/dev.jsonl --show
python score.py results/redteam.jsonl --messages redteam_messages.json --show
```

For fresh model measurements, use an empty output directory and a separate directory for disposable databases. The evaluation script resets the database before each of the five runs, selects the 15 course subset IDs for each repeat, scores each file, and prints agreement. The analysis distinguishes three failures from three identical, valid queue predictions. A model or provider change can change the measurements.

```bash
python evaluate.py --out rerun/results --work rerun/databases
python analyze.py --results rerun/results
python analyze.py --trace rerun/databases/dev.db M014
```

The report uses all 40 messages for development rates and workload, including failures. Reviewer time is proposals divided by 40, multiplied by 300 messages and 20 seconds, then divided by 3,600. The flags shown in the CLI include cancellation and safety-screen provenance. The supplied scorer separately counts warning heuristics on the final draft and actions. The red-team labels were written before testing. Evaluation code reads labels; the running agent reads the unlabelled inbox rows.

## Code walkthrough

| File | Responsibility |
| --- | --- |
| `clinic_inbox/graph.py` | LangGraph nodes and edges, prompt text, per-stage tool permissions, review flags and interrupt |
| `clinic_inbox/screen.py` | Fixed warning patterns and urgent wording |
| `clinic_inbox/record.py` | Session-scoped FHIR facts, including pending tests |
| `clinic_inbox/tools.py` | Patient-bound tools, proposal schemas and allowed replies |
| `clinic_inbox/db.py` | Validation, proposal storage, transactional execution and audit |
| `clinic_inbox/__main__.py` | Instructor CLI, checkpoint configuration, fail-safe status and reviewer interaction |
| `analyze.py`, `evaluate.py` | Evaluation protocol, workload, failure inspection and repeatability |
| `report.pdf` | Results, representative failures, limitations and proposed monitoring |

The fixed screen matches warning wording about chest discomfort, breathing difficulty, facial droop or slurred speech, loss of consciousness, and self-harm. Coverage includes a narrow romanized Hindi breathing pattern. Negation can still trigger it. The course fixtures and this screen cannot establish clinical triage performance.

The [course brief and design](https://github.com/bk-anupam/ai_in_healthcare_shared/tree/3f4d7fadf3b097e5846173702f0e074e39132ab2/project) supplied the fixtures, schema, reset script, scorer, starter tests and provider pins.
