"""Patient identity lives in closures. The model has no execution capability."""

from datetime import date
from typing import Literal

from langchain_core.tools import tool

from . import record
from .db import validate_change
from .screen import URGENT_REPLY

Queue = Literal["front_desk", "nurse", "clinician", "admin", "urgent_nurse"]
REASONS = {
    "front_desk": "Scheduling or clarification request",
    "admin": "Administrative request",
    "nurse": "Nursing review requested",
    "clinician": "Clinical decision requested",
    "urgent_nurse": "Possible warning sign requires urgent nurse review",
}
REPLIES = {
    "front_desk": "The front desk will review your request and confirm the next steps.",
    "admin": "The administration team will review your request.",
    "nurse": "A nurse will review your question and follow up.",
    "clinician": "A clinician will review your request and discuss the next steps with you.",
    "urgent_nurse": URGENT_REPLY,
}


def route(queue):
    return {
        "kind": "route",
        "queue": queue,
        "priority": "urgent" if queue == "urgent_nurse" else "routine",
        "reason": REASONS[queue],
    }


def make_tools(con, pid, today):
    @tool
    def get_patient_summary():
        """Read the logged-in patient's name, language and usual doctor's name and ID."""
        return record.summary(pid)

    @tool
    def get_appointments():
        """List this patient's appointments, including dates, service, IDs and booking status."""
        return [
            dict(r)
            for r in con.execute(
                "SELECT appointment_id,service,start,slot_id,practitioner_id,status "
                "FROM appointments WHERE patient_id=? ORDER BY start",
                (pid,),
            )
        ]

    @tool
    def search_slots(
        date_from: str,
        date_to: str,
        time_of_day: Literal["any", "morning", "afternoon"] = "any",
        doctor_id: str | None = None,
    ):
        """Find available slots for inclusive YYYY-MM-DD dates. Optional doctor_id is PR1 or PR2."""
        start = max(date.fromisoformat(date_from), date.fromisoformat(today))
        end = date.fromisoformat(date_to)
        return [
            dict(r)
            for r in con.execute(
                "SELECT slot_id,practitioner_id,start FROM slots WHERE status='free' AND substr(start,1,10) "
                "BETWEEN ? AND ? AND (?='' OR practitioner_id=?) AND (?='any' OR "
                "(substr(start,12,2)<'12' AND ?='morning') OR (substr(start,12,2)>='12' AND ?='afternoon')) "
                "ORDER BY start, practitioner_id LIMIT 12",
                (
                    str(start),
                    str(end),
                    doctor_id or "",
                    doctor_id or "",
                    time_of_day,
                    time_of_day,
                    time_of_day,
                ),
            )
        ]

    @tool
    def get_lab_status():
        """Read only this patient's test identifiers, dates and availability (never numeric values)."""
        return record.labs(pid)

    @tool
    def get_active_medications():
        """List the active medication orders on this patient's record for staff review."""
        return record.medications(pid)

    @tool
    def propose_appointment_change(
        action: Literal["book", "reschedule", "cancel"],
        appointment_id: str | None = None,
        slot_id: str | None = None,
    ):
        """Suggest one change. Cancel needs a booking ID, book a free slot, reschedule both."""
        p = {"kind": "appointment", "action": action}
        if appointment_id:
            p["appointment_id"] = appointment_id
        if slot_id:
            p["slot_id"] = slot_id
        old, _ = validate_change(con, pid, p, today)
        if old:
            p["original_slot_id"] = old["slot_id"]
        return p

    @tool
    def draft_reply(topic: Queue, test_id: str | None = None):
        """Suggest a staff-reviewed reply template. Optional observed test_id gives verified lab status."""
        text = REPLIES[topic]
        if test_id:
            lab = next((r for r in record.labs(pid) if r["test_id"] == test_id), None)
            if not lab or topic != "nurse":
                raise ValueError("Select a patient test and nurse topic for a lab status reply")
            text = (
                f"Your {lab['test']} result is {lab['status']}. The clinic can discuss it with you."
            )
        return {"kind": "reply", "text": text}

    @tool
    def route_to_staff(queue: Queue):
        """Choose one staff queue. Pass only queue. Clinic policy sets priority and reason."""
        return route(queue)

    return [
        get_patient_summary,
        get_appointments,
        search_slots,
        get_lab_status,
        get_active_medications,
        propose_appointment_change,
        draft_reply,
        route_to_staff,
    ]
