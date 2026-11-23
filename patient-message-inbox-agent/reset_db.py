"""Create a fresh clinic database from schema.sql and the fixtures.

    python reset_db.py                                   # clinic.db with the development messages
    python reset_db.py --db runs/clinic.db --messages data/messages_dev.json

OVERWRITES the database file given by --db (and SQLite's -wal/-shm side files).
Run it before every evaluation run so that each run starts from the same state.

Loads:
  - slots and appointments from the FHIR bundle's Slot, Schedule and Appointment resources
  - messages WITHOUT their authored labels (the agent must never see the labels)

After a reset, SQLite is the source of truth for the calendar. The bundle's Slot and
Appointment resources are only the starting snapshot; read patients, practitioners,
observations and medication requests from the bundle.
"""

import argparse
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE / "data" / "clinic_bundle.json"
DEFAULT_MESSAGES = HERE / "data" / "messages_dev.json"
SCHEMA = HERE / "schema.sql"


def _ref_id(reference):
    return reference["reference"].split("/")[1]


def calendar_rows(bundle):
    by_type = {}
    for entry in bundle["entry"]:
        r = entry["resource"]
        by_type.setdefault(r["resourceType"], {})[r["id"]] = r
    schedule_owner = {sid: _ref_id(s["actor"][0]) for sid, s in by_type["Schedule"].items()}
    slots = [
        (s["id"], schedule_owner[_ref_id(s["schedule"])], s["start"], s["end"], s["status"])
        for s in by_type["Slot"].values()
    ]
    appointments = []
    for a in by_type["Appointment"].values():
        refs = [p["actor"]["reference"] for p in a["participant"]]
        patient = next(r.split("/")[1] for r in refs if r.startswith("Patient/"))
        practitioner = next(r.split("/")[1] for r in refs if r.startswith("Practitioner/"))
        appointments.append(
            (a["id"], patient, practitioner, _ref_id(a["slot"][0]), a["serviceType"][0]["text"],
             a["start"], a["end"], a["status"])
        )
    return slots, appointments


def reset(db_path, bundle_path=DEFAULT_BUNDLE, messages_path=DEFAULT_MESSAGES):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)

    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    messages = json.loads(Path(messages_path).read_text(encoding="utf-8"))
    slots, appointments = calendar_rows(bundle)

    con = sqlite3.connect(db_path)
    try:
        # One transaction for schema and data: a single commit, which matters on disks with slow syncs.
        con.executescript("BEGIN;\n" + SCHEMA.read_text(encoding="utf-8"))
        con.executemany("INSERT INTO slots VALUES (?, ?, ?, ?, ?)", slots)
        con.executemany("INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?)", appointments)
        con.executemany(
            "INSERT INTO messages (message_id, patient_id, channel, identity, sent, text) VALUES (?, ?, ?, ?, ?, ?)",
            [(m["id"], m["patient_id"], m["channel"], m["identity"], m["sent"], m["text"]) for m in messages],
        )
        con.commit()
    finally:
        con.close()
    return {"slots": len(slots), "appointments": len(appointments), "messages": len(messages)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="clinic.db", help="database file to (re)create; default clinic.db")
    parser.add_argument("--bundle", default=DEFAULT_BUNDLE, help="FHIR R4 bundle with Slot/Schedule/Appointment")
    parser.add_argument("--messages", default=DEFAULT_MESSAGES, help="messages JSON file (labels are not loaded)")
    args = parser.parse_args()
    counts = reset(args.db, args.bundle, args.messages)
    print(f"Created {args.db}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
