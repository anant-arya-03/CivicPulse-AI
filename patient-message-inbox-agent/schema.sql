-- Operational database for the patient-message inbox agent (capstone project).
--
-- The clinical record (patients, doctors, lab results, medicines) stays in the
-- read-only FHIR R4 bundle data/clinic_bundle.json. This database holds the
-- clinic's working state: the calendar, the inbox, what the agent proposed,
-- what staff decided, and what was actually done.
--
-- reset_db.py creates a fresh copy from this file and the fixtures.
-- LangGraph's SqliteSaver adds its own tables (checkpoints, writes) to the same file.

PRAGMA foreign_keys = ON;

-- ---------- calendar (loaded from the bundle's Slot and Appointment resources) ----------

CREATE TABLE slots (
    slot_id         TEXT PRIMARY KEY,                -- e.g. S-PR1-1109-0900
    practitioner_id TEXT NOT NULL,                   -- PR1 or PR2 (FHIR Practitioner id)
    start           TEXT NOT NULL,                   -- ISO 8601 with offset, e.g. 2026-11-09T09:00:00+05:30
    "end"           TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('free', 'busy'))
);

CREATE TABLE appointments (
    appointment_id  TEXT PRIMARY KEY,                -- A01 ... ; new bookings get the next number
    patient_id      TEXT NOT NULL,                   -- FHIR Patient id, e.g. P07
    practitioner_id TEXT NOT NULL,
    slot_id         TEXT NOT NULL REFERENCES slots (slot_id),
    service         TEXT NOT NULL,                   -- e.g. "Diabetes review"
    start           TEXT NOT NULL,
    "end"           TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('booked', 'cancelled'))
);

-- ---------- inbox ----------

-- One row per incoming patient message. Authored labels are NOT stored here:
-- the agent must never see them.
CREATE TABLE messages (
    message_id  TEXT PRIMARY KEY,                    -- e.g. M001; also used as the LangGraph thread_id
    patient_id  TEXT NOT NULL,                       -- from the verified login, not from the message text
    channel     TEXT NOT NULL,                       -- 'portal' in all fixtures
    identity    TEXT NOT NULL,                       -- how the sender was identified: 'portal_login'
    sent        TEXT NOT NULL,                       -- ISO 8601; its date is the agent's "today"
    text        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'awaiting_review', 'done', 'error')),
    error       TEXT                                 -- exception name if the run failed
);

-- ---------- agent output and human decisions ----------

-- Every proposal the agent (or the safety screen) made for a message.
-- Proposals change nothing by themselves.
CREATE TABLE proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL REFERENCES messages (message_id),
    patient_id  TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('appointment', 'reply', 'route')),
    payload     TEXT NOT NULL,                       -- JSON: the proposal's fields (action, slot_id, text, queue, ...)
    source      TEXT NOT NULL CHECK (source IN ('agent', 'safety_screen')),
    flags       TEXT NOT NULL DEFAULT '[]',          -- JSON list of review flags shown to staff
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'rejected', 'applied', 'failed'))
);

-- Append-only record of every human decision and its result.
CREATE TABLE audit_log (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    proposal_id INTEGER NOT NULL REFERENCES proposals (proposal_id),
    reviewer    TEXT NOT NULL,                       -- a named person, never the agent
    decision    TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    flags_shown TEXT NOT NULL,                       -- JSON list: what the reviewer saw at decision time
    result      TEXT NOT NULL                        -- JSON: {"status": "done"} or {"status": "failed", "reason": ...}
);

CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

-- ---------- effects of approved proposals ----------

-- Approved replies waiting to be sent. Nothing in this project actually sends them.
CREATE TABLE outbox (
    outbox_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL REFERENCES proposals (proposal_id),
    patient_id  TEXT NOT NULL,
    text        TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    at          TEXT NOT NULL
);

-- Approved routings: the work lists that clinic staff pick up.
CREATE TABLE staff_queue (
    item_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL REFERENCES proposals (proposal_id),
    message_id  TEXT NOT NULL REFERENCES messages (message_id),
    patient_id  TEXT NOT NULL,
    queue       TEXT NOT NULL CHECK (queue IN ('front_desk', 'nurse', 'clinician', 'admin', 'urgent_nurse')),
    priority    TEXT NOT NULL CHECK (priority IN ('routine', 'urgent')),
    reason      TEXT NOT NULL,
    at          TEXT NOT NULL
);

CREATE INDEX idx_slots_start ON slots (start);
CREATE INDEX idx_appointments_patient ON appointments (patient_id);
CREATE INDEX idx_proposals_message ON proposals (message_id);
