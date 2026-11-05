"""Enums for reply monitoring and follow-ups. Stored as VARCHAR, validated by these StrEnums."""

from enum import StrEnum


class ReplyKind(StrEnum):
    """What a department's reply means. Set by the AI (if confident) or by the citizen."""

    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"  # "we received it" (often with a reference number)
    IN_PROGRESS = "IN_PROGRESS"  # "work has started / a team is assigned"
    RESOLVED_CLAIM = "RESOLVED_CLAIM"  # "it's fixed": only the citizen can confirm that
    REQUEST_FOR_INFO = "REQUEST_FOR_INFO"  # the department needs something from the citizen
    REJECTION = "REJECTION"  # declined, or "not our department"
    UNRELATED = "UNRELATED"  # auto-replies, spam, anything not about this complaint


class ReplyKindSource(StrEnum):
    AI = "AI"
    CITIZEN = "CITIZEN"


class ActionType(StrEnum):
    # "Has the department answered by its deadline? If not, suggest a reminder (or escalation)."
    FOLLOWUP_CHECK = "FOLLOWUP_CHECK"


class ActionStatus(StrEnum):
    PENDING = "PENDING"  # waiting for its time
    RUNNING = "RUNNING"  # claimed by a worker
    DONE = "DONE"  # ran and did something (drafted a reminder, recommended escalation)
    SKIPPED = "SKIPPED"  # ran, but the situation had changed, so nothing was needed
    FAILED = "FAILED"  # kept failing after the maximum number of attempts
    CANCELLED = "CANCELLED"  # no longer needed (reply received, complaint resolved or withdrawn)


class CheckTrigger(StrEnum):
    """What started the waiting period that a FOLLOWUP_CHECK ends."""

    COMPLAINT_SENT = "COMPLAINT_SENT"
    FOLLOWUP_SENT = "FOLLOWUP_SENT"
    FOLLOWUP_DISMISSED = "FOLLOWUP_DISMISSED"
    PROGRESS_REPLY = "PROGRESS_REPLY"  # acknowledged / in progress, then silence
    UNRELATED_REPLY = "UNRELATED_REPLY"  # e.g. an auto-reply: keep waiting for a real answer


REPLY_KIND_LABELS: dict[ReplyKind, str] = {
    ReplyKind.ACKNOWLEDGMENT: "acknowledgment",
    ReplyKind.IN_PROGRESS: "work in progress",
    ReplyKind.RESOLVED_CLAIM: "says the issue is resolved",
    ReplyKind.REQUEST_FOR_INFO: "request for more information",
    ReplyKind.REJECTION: "complaint declined",
    ReplyKind.UNRELATED: "not about this complaint",
}
