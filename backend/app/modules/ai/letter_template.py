"""Assemble the formal complaint letter.

Design: the AI writes only three short pieces of wording (ComplaintLetterProse). Everything
factual (reference, issue type, location, date, photo count, the citizen's name) is filled in
here from the database. So whatever the model writes, the facts in the letter are correct.

`template_prose()` is the manual fallback: the same letter, worded without any AI.
"""

import json
from typing import Any

from app.modules.ai.schemas import ComplaintLetterProse
from app.modules.complaints.constants import CATEGORY_LABELS, Category, Severity
from app.modules.complaints.models import Complaint
from app.modules.users.models import User

_SEVERITY_LABELS = {
    Severity.LOW: "Low",
    Severity.MEDIUM: "Medium",
    Severity.HIGH: "High (possible risk to safety)",
    Severity.UNKNOWN: "Not assessed",
}

_REQUESTED_ACTIONS: dict[Category, str] = {
    Category.ROAD_POTHOLE: "inspect the road and repair the damaged surface",
    Category.BROKEN_STREETLIGHT: "inspect and repair or replace the streetlight",
    Category.GARBAGE_OVERFLOW: "arrange for the waste to be cleared and the bins emptied",
    Category.OPEN_DRAIN: "inspect the drain and cover or repair it",
    Category.WATER_LEAKAGE: "inspect the leak and repair the damaged pipe or fitting",
    Category.WATERLOGGING: "inspect the area and clear the drainage so the water can flow away",
    Category.DAMAGED_INFRASTRUCTURE: "inspect and repair the damaged public property",
    Category.OTHER: "inspect the issue and take the appropriate action",
}


def build_facts(complaint: Complaint, user: User) -> dict[str, Any]:
    """The confirmed facts the letter is based on (also what the AI is shown)."""
    category = Category(complaint.category) if complaint.category else Category.OTHER
    severity = Severity(complaint.severity) if complaint.severity else Severity.UNKNOWN
    location_parts = [
        complaint.address_line,
        complaint.locality,
        complaint.city,
        complaint.state,
        complaint.postal_code,
    ]
    photos = [e for e in complaint.evidence if e.evidence_type == "ORIGINAL"]
    include_name = (user.privacy_settings or {}).get("include_name_in_complaints", True)
    return {
        "reference": complaint.public_reference,
        "title": complaint.title or "",
        "category_label": CATEGORY_LABELS[category],
        "category": category.value,
        "severity_label": _SEVERITY_LABELS[severity],
        "citizen_description": complaint.description or "",
        "location_summary": ", ".join(p for p in location_parts if p),
        "coordinates": (
            f"{float(complaint.latitude):.6f}, {float(complaint.longitude):.6f}"
            if complaint.latitude is not None and complaint.longitude is not None
            else None
        ),
        "observed_on": (
            complaint.observed_at.strftime("%d %B %Y, %H:%M UTC") if complaint.observed_at else None
        ),
        "photo_count": len(photos),
        "citizen_name": user.name if include_name else None,
    }


def facts_as_prompt_text(facts: dict[str, Any]) -> str:
    """Facts as JSON inside <facts> tags. '<' is escaped so citizen text can't close the tag."""
    payload = json.dumps(facts, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return f"<facts>\n{payload}\n</facts>\n\nWrite the subject, issue_summary and requested_action."


def template_prose(facts: dict[str, Any]) -> ComplaintLetterProse:
    """The no-AI fallback: plain wording built from the citizen's own words."""
    category = Category(facts["category"])
    issue = facts["category_label"].lower()
    place = facts["location_summary"] or "the location given below"
    description = facts["citizen_description"].strip()
    summary = f"I would like to report a problem: {issue} at {place}."
    if description:
        summary += f" {description}"
    # model_construct skips the AI length limits: this is our own text, and the citizen's
    # description must never be cut short.
    return ComplaintLetterProse.model_construct(
        subject=f"Complaint: {facts['title'] or facts['category_label']} ({facts['reference']})",
        issue_summary=summary,
        requested_action=(
            f"I kindly request that you {_REQUESTED_ACTIONS[category]} as soon as possible."
        ),
    )


def render_letter(prose: ComplaintLetterProse, facts: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, body). The citizen can edit both before anything is sent."""
    details = [
        f"- Reference: {facts['reference']}",
        f"- Type of issue: {facts['category_label']}",
        f"- Location: {facts['location_summary'] or 'not specified'}",
    ]
    if facts["coordinates"]:
        details.append(f"- Map coordinates: {facts['coordinates']}")
    if facts["observed_on"]:
        details.append(f"- Observed on: {facts['observed_on']}")
    details.append(f"- Severity (reporter's assessment): {facts['severity_label']}")
    count = facts["photo_count"]
    details.append(f"- Photo evidence: {count} photo{'s' if count != 1 else ''} attached")

    signature = facts["citizen_name"] or "A concerned resident"
    body = "\n".join(
        [
            "Dear Sir or Madam,",
            "",
            prose.issue_summary,
            "",
            "Details of the issue:",
            *details,
            "",
            prose.requested_action,
            "",
            "Thank you for your attention to this matter. I would be grateful for an "
            "acknowledgement and an update once the issue has been addressed.",
            "",
            "Yours faithfully,",
            signature,
        ]
    )
    return prose.subject, body
