"""Monitoring rules as plain functions (no database, no AI), so each rule has a simple test.

These rules, not the AI, decide what happens after a reply or a missed deadline.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.complaints.constants import MONITORED_STATUSES, ComplaintStatus
from app.modules.complaints.status_machine import can_transition
from app.modules.monitoring.constants import CheckTrigger, ReplyKind

# ── Deadlines ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Deadline:
    due_at: datetime
    official: bool  # True: based on the response time listed for the department
    basis: str  # plain-language explanation shown to the citizen


def next_check(
    trigger: CheckTrigger,
    *,
    at: datetime,
    submitted_at: datetime | None,
    service_timeline_days: int | None,
    first_after_days: int,
    interval_days: int,
) -> Deadline:
    """When to check whether the department has answered.

    - After the complaint: the department's listed response time, or our default.
    - After a reminder (or a reminder the citizen chose not to send): the follow-up interval.
    - After "received" / "in progress" and then silence: the later of the department's own
      deadline and one interval after its last update. Departments get time to do the work.
    """
    first_days = service_timeline_days or first_after_days
    if service_timeline_days:
        policy = f"the response time listed for this department ({service_timeline_days} days)"
    else:
        policy = (
            "CivicPulse's default of "
            f"{first_after_days} days (no response time is listed for this department)"
        )

    if trigger == CheckTrigger.COMPLAINT_SENT:
        return Deadline(at + timedelta(days=first_days), bool(service_timeline_days), policy)

    if trigger == CheckTrigger.PROGRESS_REPLY:
        policy_due = (submitted_at or at) + timedelta(days=first_days)
        silence_due = at + timedelta(days=interval_days)
        if policy_due >= silence_due:
            return Deadline(policy_due, bool(service_timeline_days), policy)
        return Deadline(
            silence_due, False, f"{interval_days} days after the department's last update"
        )

    after = {
        CheckTrigger.FOLLOWUP_SENT: "your last reminder",
        CheckTrigger.FOLLOWUP_DISMISSED: "you chose not to send a reminder",
        CheckTrigger.UNRELATED_REPLY: "the last message",
    }[trigger]
    return Deadline(
        at + timedelta(days=interval_days), False, f"{interval_days} days after {after}"
    )


# ── Reminders ───────────────────────────────────────────────────────────────


def followup_blocker(
    *,
    status: ComplaintStatus,
    sent_count: int,
    max_count: int,
    has_open_followup: bool,
) -> str | None:
    """Why a new reminder must NOT be drafted or sent right now (None = it's allowed)."""
    if status not in MONITORED_STATUSES:
        return "The complaint is no longer waiting for a reply."
    if sent_count >= max_count:
        return f"The limit of {max_count} reminder(s) for this complaint has been reached."
    if has_open_followup:
        return "Another reminder is already waiting for your approval."
    return None


# ── Replies ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReplyEffect:
    new_status: ComplaintStatus | None  # None = no status change
    status_note: str  # timeline text for the status change
    stop_reminders: bool  # cancel pending checks and unsent reminder drafts
    keep_checking: bool  # schedule a new deadline check
    recommend_escalation: bool
    stop_reason: str


_TARGET_STATUS = {
    ReplyKind.ACKNOWLEDGMENT: ComplaintStatus.ACKNOWLEDGED,
    ReplyKind.IN_PROGRESS: ComplaintStatus.IN_PROGRESS,
    ReplyKind.RESOLVED_CLAIM: ComplaintStatus.RESOLVED_PENDING_VERIFICATION,
}

_STATUS_NOTES = {
    ReplyKind.ACKNOWLEDGMENT: "The department acknowledged your complaint.",
    ReplyKind.IN_PROGRESS: "The department says work on your complaint is in progress.",
    ReplyKind.RESOLVED_CLAIM: (
        "The department says the issue is resolved. Only you can confirm that it is fixed."
    ),
}


def reply_effect(kind: ReplyKind, current: ComplaintStatus) -> ReplyEffect:
    """What a reply of this kind does. The strongest possible effect is "the department says
    it's fixed", which still needs the citizen to verify. A reply can never close a complaint,
    mark it verified, or send anything."""
    target = _TARGET_STATUS.get(kind)
    new_status = target if target and can_transition(current, target) else None
    status_after = new_status or current

    if kind in (ReplyKind.ACKNOWLEDGMENT, ReplyKind.IN_PROGRESS):
        return ReplyEffect(
            new_status,
            _STATUS_NOTES[kind],
            stop_reminders=True,
            keep_checking=status_after in MONITORED_STATUSES,
            recommend_escalation=False,
            stop_reason="the department replied",
        )
    if kind == ReplyKind.RESOLVED_CLAIM:
        return ReplyEffect(
            new_status,
            _STATUS_NOTES[kind],
            stop_reminders=True,
            keep_checking=False,
            recommend_escalation=False,
            stop_reason="the department says the issue is resolved",
        )
    if kind == ReplyKind.REQUEST_FOR_INFO:
        return ReplyEffect(
            None,
            "",
            stop_reminders=True,
            keep_checking=False,
            recommend_escalation=False,
            stop_reason="the department asked you for more information",
        )
    if kind == ReplyKind.REJECTION:
        return ReplyEffect(
            None,
            "",
            stop_reminders=True,
            keep_checking=False,
            recommend_escalation=True,
            stop_reason="the department declined the complaint",
        )
    # UNRELATED (auto-replies, spam): changes nothing; the existing deadline still applies.
    return ReplyEffect(None, "", False, False, False, "")


def should_auto_apply(confidence: str) -> bool:
    """Apply the AI's reading of a reply automatically only if it isn't unsure."""
    return confidence in ("HIGH", "MEDIUM")


# ── Reference numbers ───────────────────────────────────────────────────────

# "reference number is ABC-123", "Ref. No.: 2026/RD/0412", "ticket #A1234", "docket: X-77"
_LABELLED_REFERENCE = re.compile(
    r"(?i)\b(?:reference|ref\.?|ticket|docket|token|grievance|complaint|case)"
    r"(?:\s*(?:number|no\.?|id))?\s*(?:is\b|:|#|-)?\s*"
    r"([A-Za-z0-9][A-Za-z0-9/-]{2,38}[A-Za-z0-9])"
)
# Letters, digits, "/" and "-" only, with at least one digit; 4-40 characters.
_SAFE_REFERENCE = re.compile(r"^(?=.*\d)[A-Z0-9][A-Z0-9/-]{2,38}[A-Z0-9]$")


def normalise_reference(candidate: str | None) -> str | None:
    if not candidate:
        return None
    value = candidate.strip().upper()
    return value if _SAFE_REFERENCE.match(value) else None


def find_reference_number(text: str, *, own_reference: str) -> str | None:
    """Deterministic extraction (works without AI). Ignores CivicPulse's own reference."""
    for match in _LABELLED_REFERENCE.finditer(text):
        value = normalise_reference(match.group(1))
        if value and value != own_reference.upper():
            return value
    return None


def accept_reference(candidate: str | None, text: str, *, own_reference: str) -> str | None:
    """An AI-suggested reference number is kept only if it has a safe format AND appears
    word-for-word in the reply, so the model can't invent one."""
    value = normalise_reference(candidate)
    if not value or value == own_reference.upper():
        return None
    return value if value in text.upper() else None
