"""The only operational writes happen in record_proposals and execute."""

import json
import sqlite3
from datetime import UTC, datetime


def connect(path):
    con = sqlite3.connect(path, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def now():
    return datetime.now(UTC).isoformat()


class CalendarConflict(ValueError):
    pass


def validate_change(con, pid, p, today):
    action = p["action"]
    old = new = None
    if action not in {"cancel", "reschedule", "book"}:
        raise ValueError("Unknown appointment action")
    if (action == "book" and p.get("appointment_id")) or (action == "cancel" and p.get("slot_id")):
        raise ValueError("Unexpected appointment or slot identifier")
    if action != "book":
        old = con.execute(
            "SELECT * FROM appointments WHERE patient_id=? AND appointment_id=? "
            "AND status='booked'",
            (pid, p.get("appointment_id")),
        ).fetchone()
        if (
            not old
            or old["start"][:10] < today
            or p.get("original_slot_id", old["slot_id"]) != old["slot_id"]
        ):
            raise CalendarConflict("Original booking unavailable or changed")
    if action != "cancel":
        new = con.execute(
            "SELECT * FROM slots WHERE slot_id=? AND status='free' AND substr(start,1,10)>=?",
            (p.get("slot_id"), today),
        ).fetchone()
        if not new:
            raise CalendarConflict("Requested slot unavailable")
        clash = con.execute(
            "SELECT 1 FROM appointments WHERE patient_id=? AND status='booked' "
            'AND start < ? AND "end" > ? AND appointment_id != ?',
            (pid, new["end"], new["start"], p.get("appointment_id") or ""),
        ).fetchone()
        if clash:
            raise CalendarConflict("Overlapping patient booking")
    return old, new


def apply_change(con, pid, p, today):
    old, new = validate_change(con, pid, p, today)
    if old:
        con.execute("UPDATE slots SET status='free' WHERE slot_id=?", (old["slot_id"],))
    if not new:
        con.execute(
            "UPDATE appointments SET status='cancelled' WHERE appointment_id=?",
            (old["appointment_id"],),
        )
        return
    con.execute("UPDATE slots SET status='busy' WHERE slot_id=?", (new["slot_id"],))
    timing = (new["practitioner_id"], new["slot_id"], new["start"], new["end"])
    if old:
        con.execute(
            'UPDATE appointments SET practitioner_id=?, slot_id=?, start=?, "end"=? WHERE appointment_id=?',
            (*timing, old["appointment_id"]),
        )
    else:
        number = con.execute(
            "SELECT COALESCE(MAX(CAST(substr(appointment_id,2) AS INTEGER)),0)+1 FROM appointments"
        ).fetchone()[0]
        con.execute(
            "INSERT INTO appointments (appointment_id, patient_id, practitioner_id, slot_id, start, "
            "\"end\", service, status) VALUES (?,?,?,?,?,?,?,'booked')",
            (f"A{number:02}", pid, *timing, "Clinic visit"),
        )


def record_proposals(con, mid, pid, items, source, flags):
    with con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            "SELECT proposal_id FROM proposals WHERE message_id=? ORDER BY proposal_id", (mid,)
        ).fetchall()
        if existing:  # Replay after a checkpoint interruption
            return [r[0] for r in existing]
        ids = []
        for p, marks in zip(items, flags, strict=True):
            row = con.execute(
                "INSERT INTO proposals (message_id,patient_id,kind,payload,source,flags,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, pid, p["kind"], json.dumps(p), source, json.dumps(marks), now()),
            )
            ids.append(row.lastrowid)
        con.execute("UPDATE messages SET status='awaiting_review' WHERE message_id=?", (mid,))
        return ids


def execute(con, mid, decision):
    reviewer = decision["reviewer"].strip()
    choices = decision["choices"]
    with con:
        con.execute("BEGIN IMMEDIATE")
        msg = con.execute("SELECT * FROM messages WHERE message_id=?", (mid,)).fetchone()
        if msg["status"] == "done":
            return  # the transaction committed before the last graph checkpoint
        rows = con.execute(
            "SELECT * FROM proposals WHERE message_id=? AND status='pending' ORDER BY proposal_id",
            (mid,),
        ).fetchall()
        if (
            not reviewer
            or not rows
            or msg["status"] != "awaiting_review"
            or set(choices) != {str(r["proposal_id"]) for r in rows}
            or any(v not in {"approved", "rejected"} for v in choices.values())
        ):
            raise ValueError("Incomplete review decision")
        for r in rows:
            prop_id, pid = r["proposal_id"], msg["patient_id"]
            choice = choices[str(prop_id)]
            p = json.loads(r["payload"])
            status = "rejected"
            result = {"status": "rejected"}
            if choice == "approved":
                status, result = "applied", {"status": "done"}
                if r["kind"] == "appointment":
                    try:
                        apply_change(con, pid, p, msg["sent"][:10])
                    except CalendarConflict as exc:
                        status, result = "failed", {"status": "failed", "reason": str(exc)}
                elif r["kind"] == "route":
                    con.execute(
                        "INSERT INTO staff_queue (proposal_id,message_id,patient_id,queue,priority,reason,at) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (prop_id, mid, pid, p["queue"], p["priority"], p["reason"], now()),
                    )
                else:
                    con.execute(
                        "INSERT INTO outbox (proposal_id,patient_id,text,approved_by,at) VALUES (?,?,?,?,?)",
                        (prop_id, pid, p["text"], reviewer, now()),
                    )
            con.execute("UPDATE proposals SET status=? WHERE proposal_id=?", (status, prop_id))
            con.execute(
                "INSERT INTO audit_log (at,proposal_id,reviewer,decision,flags_shown,result) "
                "VALUES (?,?,?,?,?,?)",
                (now(), prop_id, reviewer, choice, r["flags"], json.dumps(result)),
            )
        con.execute("UPDATE messages SET status='done' WHERE message_id=?", (mid,))
