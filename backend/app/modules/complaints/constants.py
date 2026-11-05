"""Enums for complaints. Stored in the database as plain VARCHAR values.

To add a category: add a member to `Category`, add its label/icon in
frontend/src/features/complaints/constants.ts, and (from Milestone 4) list it in the
`supported_categories` of the authorities that handle it. No migration needed.
"""

from enum import StrEnum


class ComplaintStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED_PENDING_VERIFICATION = "RESOLVED_PENDING_VERIFICATION"
    VERIFIED_RESOLVED = "VERIFIED_RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class Category(StrEnum):
    ROAD_POTHOLE = "ROAD_POTHOLE"
    BROKEN_STREETLIGHT = "BROKEN_STREETLIGHT"
    GARBAGE_OVERFLOW = "GARBAGE_OVERFLOW"
    OPEN_DRAIN = "OPEN_DRAIN"
    WATER_LEAKAGE = "WATER_LEAKAGE"
    WATERLOGGING = "WATERLOGGING"
    DAMAGED_INFRASTRUCTURE = "DAMAGED_INFRASTRUCTURE"
    OTHER = "OTHER"


CATEGORY_LABELS: dict[Category, str] = {
    Category.ROAD_POTHOLE: "Road pothole",
    Category.BROKEN_STREETLIGHT: "Broken streetlight",
    Category.GARBAGE_OVERFLOW: "Overflowing garbage",
    Category.OPEN_DRAIN: "Open drain",
    Category.WATER_LEAKAGE: "Water leakage",
    Category.WATERLOGGING: "Waterlogging",
    Category.DAMAGED_INFRASTRUCTURE: "Damaged public infrastructure",
    Category.OTHER: "Other civic issue",
}


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class EventType(StrEnum):
    COMPLAINT_CREATED = "COMPLAINT_CREATED"
    EVIDENCE_UPLOADED = "EVIDENCE_UPLOADED"
    EVIDENCE_REMOVED = "EVIDENCE_REMOVED"
    DETAILS_UPDATED = "DETAILS_UPDATED"
    LOCATION_CONFIRMED = "LOCATION_CONFIRMED"
    STATUS_CHANGED = "STATUS_CHANGED"
    COMPLAINT_CANCELLED = "COMPLAINT_CANCELLED"
    COMPLAINT_CLOSED = "COMPLAINT_CLOSED"
    AI_ANALYSIS_COMPLETED = "AI_ANALYSIS_COMPLETED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    COMPLAINT_DRAFT_GENERATED = "COMPLAINT_DRAFT_GENERATED"
    AUTHORITY_SELECTED = "AUTHORITY_SELECTED"
    COMPLAINT_APPROVED = "COMPLAINT_APPROVED"
    APPROVAL_WITHDRAWN = "APPROVAL_WITHDRAWN"
    SUBMISSION_ATTEMPTED = "SUBMISSION_ATTEMPTED"
    SUBMISSION_ACCEPTED = "SUBMISSION_ACCEPTED"
    SUBMISSION_FAILED = "SUBMISSION_FAILED"
    # Milestone 5: replies, reminders, escalation
    REPLY_RECEIVED = "REPLY_RECEIVED"
    REPLY_CLASSIFIED = "REPLY_CLASSIFIED"
    REFERENCE_NUMBER_RECORDED = "REFERENCE_NUMBER_RECORDED"
    FOLLOWUP_SUGGESTED = "FOLLOWUP_SUGGESTED"
    FOLLOWUP_APPROVED = "FOLLOWUP_APPROVED"
    FOLLOWUP_SENT = "FOLLOWUP_SENT"
    FOLLOWUP_FAILED = "FOLLOWUP_FAILED"
    FOLLOWUP_DISMISSED = "FOLLOWUP_DISMISSED"
    FOLLOWUPS_STOPPED = "FOLLOWUPS_STOPPED"
    ESCALATION_RECOMMENDED = "ESCALATION_RECOMMENDED"
    # Milestone 6: checking a repair
    RESOLUTION_EVIDENCE_UPLOADED = "RESOLUTION_EVIDENCE_UPLOADED"
    RESOLUTION_ASSESSED = "RESOLUTION_ASSESSED"
    RESOLUTION_CONFIRMED = "RESOLUTION_CONFIRMED"
    RESOLUTION_DISPUTED = "RESOLUTION_DISPUTED"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"


class Actor(StrEnum):
    CITIZEN = "CITIZEN"
    SYSTEM = "SYSTEM"
    AI = "AI"
    AUTHORITY = "AUTHORITY"


# Statuses in which the citizen may still edit details and photos.
EDITABLE_STATUSES = frozenset({ComplaintStatus.DRAFT, ComplaintStatus.PENDING_REVIEW})

# Sent and waiting for the department: reminders may be suggested only in these statuses.
MONITORED_STATUSES = frozenset(
    {
        ComplaintStatus.SUBMITTED,
        ComplaintStatus.ACKNOWLEDGED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.REOPENED,
    }
)

# The citizen may add an "after" photo and decide whether the problem is fixed.
VERIFIABLE_STATUSES = frozenset(
    {*MONITORED_STATUSES, ComplaintStatus.RESOLVED_PENDING_VERIFICATION}
)

# "Active" = sent to a department and not yet finished (used by the dashboard).
ACTIVE_STATUSES = frozenset(
    {
        ComplaintStatus.SUBMITTED,
        ComplaintStatus.ACKNOWLEDGED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED_PENDING_VERIFICATION,
        ComplaintStatus.REOPENED,
    }
)
