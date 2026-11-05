"""The complaint status lifecycle: the single source of truth for which status changes are allowed.

See docs/workflows.md section 1 for the diagram. Never change `complaint.status` directly;
call `complaints.service.change_status`, which uses `ensure_transition` and records an event.
"""

from app.core.errors import InvalidTransitionError
from app.modules.complaints.constants import ComplaintStatus as S

ALLOWED_TRANSITIONS: dict[S, frozenset[S]] = {
    S.DRAFT: frozenset({S.PENDING_REVIEW, S.CANCELLED}),
    S.PENDING_REVIEW: frozenset({S.DRAFT, S.SUBMITTED, S.CANCELLED}),
    S.SUBMITTED: frozenset(
        {S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED_PENDING_VERIFICATION, S.CLOSED, S.CANCELLED}
    ),
    S.ACKNOWLEDGED: frozenset({S.IN_PROGRESS, S.RESOLVED_PENDING_VERIFICATION, S.CLOSED}),
    S.IN_PROGRESS: frozenset({S.RESOLVED_PENDING_VERIFICATION, S.CLOSED}),
    S.RESOLVED_PENDING_VERIFICATION: frozenset({S.VERIFIED_RESOLVED, S.REOPENED}),
    S.VERIFIED_RESOLVED: frozenset({S.CLOSED, S.REOPENED}),
    S.REOPENED: frozenset(
        {S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED_PENDING_VERIFICATION, S.CLOSED}
    ),
    S.CLOSED: frozenset({S.REOPENED}),
    S.CANCELLED: frozenset(),  # terminal
}

_LABELS: dict[S, str] = {
    S.DRAFT: "a draft",
    S.PENDING_REVIEW: "pending review",
    S.SUBMITTED: "submitted",
    S.ACKNOWLEDGED: "acknowledged",
    S.IN_PROGRESS: "in progress",
    S.RESOLVED_PENDING_VERIFICATION: "awaiting your verification",
    S.VERIFIED_RESOLVED: "verified as resolved",
    S.CLOSED: "closed",
    S.REOPENED: "reopened",
    S.CANCELLED: "cancelled",
}


def can_transition(current: S, new: S) -> bool:
    return new in ALLOWED_TRANSITIONS[current]


def ensure_transition(current: S, new: S) -> None:
    if not can_transition(current, new):
        raise InvalidTransitionError(
            f"A complaint that is {_LABELS[current]} cannot be changed to {_LABELS[new]}.",
            {"current_status": current.value, "requested_status": new.value},
        )
