"""Assemble a follow-up reminder.

Same design as letter_template.py: the AI writes only two short pieces of wording
(FollowupProse). Every fact (references, dates, place, the department's listed response time)
is filled in here from the database. `template_followup_prose()` is the no-AI fallback.
"""

import json
from datetime import datetime
from typing import Any

from app.modules.ai.schemas import FollowupProse
from app.modules.complaints.constants import CATEGORY_LABELS, Category
from app.modules.complaints.models import Complaint
from app.modules.users.models import User


def _day(value: datetime | None) -> str | None:
    return value.strftime("%d %B %Y") if value else None


def build_followup_facts(
    complaint: Complaint,
    user: User,
    *,
    number: int,
    previous_reminder_at: datetime | None,
    department_replied: bool,
) -> dict[str, Any]:
    category = Category(complaint.category) if complaint.category else Category.OTHER
    authority = complaint.authority
    include_name = (user.privacy_settings or {}).get("include_name_in_complaints", True)
    place = ", ".join(p for p in [complaint.address_line, complaint.locality, complaint.city] if p)
    return {
        "reminder_number": number,
        "reference": complaint.public_reference,
        "department_reference": complaint.authority_reference_number,
        "title": complaint.title or CATEGORY_LABELS[category],
        "category_label": CATEGORY_LABELS[category],
        "location_summary": place,
        "submitted_on": _day(complaint.submitted_at),
        "previous_reminder_on": _day(previous_reminder_at),
        "department_name": authority.name if authority else None,
        "listed_response_days": authority.service_timeline_days if authority else None,
        "department_replied": department_replied,
        "citizen_name": user.name if include_name else None,
    }


def facts_as_prompt_text(facts: dict[str, Any]) -> str:
    payload = json.dumps(facts, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return f"<facts>\n{payload}\n</facts>\n\nWrite the opening and requested_action."


def template_followup_prose(facts: dict[str, Any]) -> FollowupProse:
    """The no-AI fallback wording."""
    issue = facts["category_label"].lower()
    place = facts["location_summary"] or "the reported location"
    if facts["department_replied"]:
        opening = (
            f"Thank you for your earlier reply about the {issue} at {place}. "
            "I am writing to ask for an update, as I have not heard anything further."
        )
    else:
        opening = (
            f"I am writing to follow up on my complaint about the {issue} at {place}. "
            "I have not yet received a reply."
        )
    return FollowupProse.model_construct(
        opening=opening,
        requested_action=(
            "I would be grateful for an update on the status of this complaint and the "
            "expected date of action."
        ),
    )


def _details(facts: dict[str, Any]) -> list[str]:
    details = [f"- Our reference: {facts['reference']}"]
    if facts["department_reference"]:
        details.append(f"- Your reference: {facts['department_reference']}")
    details.append(f"- Issue: {facts['title']} ({facts['category_label']})")
    if facts["location_summary"]:
        details.append(f"- Location: {facts['location_summary']}")
    if facts["submitted_on"]:
        details.append(f"- Complaint submitted on: {facts['submitted_on']}")
    if facts["previous_reminder_on"]:
        details.append(f"- Previous reminder sent on: {facts['previous_reminder_on']}")
    if facts["listed_response_days"]:
        details.append(f"- Listed response time: {facts['listed_response_days']} days")
    return details


def render_followup(prose: FollowupProse, facts: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, body). The citizen can edit both before approving."""
    details = _details(facts)
    reference = facts["department_reference"] or facts["reference"]
    subject = f"Reminder {facts['reminder_number']}: {facts['title']} ({reference})"
    body = "\n".join(
        [
            "Dear Sir or Madam,",
            "",
            prose.opening,
            "",
            "Details of my complaint:",
            *details,
            "",
            prose.requested_action,
            "",
            "Thank you for your attention to this matter.",
            "",
            "Yours faithfully,",
            facts["citizen_name"] or "A concerned resident",
        ]
    )
    return subject[:200], body


def render_not_fixed_notice(
    facts: dict[str, Any], *, came_back: bool, checked_on: str, notes: str | None
) -> tuple[str, str]:
    """The message telling the department the problem is not (or no longer) fixed. Template
    only, no AI: it states the citizen's own finding. The citizen edits and approves it."""
    if came_back:
        opening = (
            f"I am writing about my earlier complaint about the {facts['category_label'].lower()}"
            f" at {facts['location_summary'] or 'the reported location'}. The problem had been"
            f" resolved, but when I checked on {checked_on} it had come back."
        )
    else:
        opening = (
            "Thank you for letting me know that this issue had been resolved. However, when I"
            f" checked the location on {checked_on}, the problem was still there."
        )
    lines = [
        "Dear Sir or Madam,",
        "",
        opening,
        "",
        "Details of my complaint:",
        *_details(facts),
    ]
    if notes:
        lines += ["", "What I found:", notes]
    lines += [
        "",
        "I kindly request that the site is inspected again and the repair completed.",
        "",
        "Thank you for your attention to this matter.",
        "",
        "Yours faithfully,",
        facts["citizen_name"] or "A concerned resident",
    ]
    reference = facts["department_reference"] or facts["reference"]
    subject = f"Not resolved: {facts['title']} ({reference})"
    return subject[:200], "\n".join(lines)
