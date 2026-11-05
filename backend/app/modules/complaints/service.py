"""Complaint business logic: drafts, listing, status changes, timeline, and dashboard numbers."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.common.time import utc_now
from app.core.errors import BusinessRuleError, InvalidTransitionError, NotFoundError
from app.modules.complaints.constants import (
    ACTIVE_STATUSES,
    EDITABLE_STATUSES,
    VERIFIABLE_STATUSES,
    Actor,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint, ComplaintEvent, complaint_reference_seq
from app.modules.complaints.schemas import (
    ActivityItem,
    ComplaintAction,
    ComplaintCreate,
    ComplaintEventRead,
    ComplaintListItem,
    ComplaintListParams,
    ComplaintRead,
    ComplaintUpdate,
    DashboardStats,
    DashboardSummary,
)
from app.modules.complaints.status_machine import can_transition, ensure_transition
from app.modules.users.models import User

MAX_ORIGINAL_PHOTOS = 5

_LOCATION_FIELDS = {
    "address_line",
    "locality",
    "city",
    "state",
    "postal_code",
    "country",
    "latitude",
    "longitude",
}

# Human-readable names used in timeline descriptions.
_FIELD_LABELS = {
    "title": "title",
    "description": "description",
    "category": "category",
    "severity": "severity",
    "address_line": "address",
    "locality": "locality",
    "city": "city",
    "state": "state",
    "postal_code": "postal code",
    "country": "country",
    "latitude": "map pin",
    "longitude": "map pin",
    "observed_at": "observation time",
    "draft_subject": "complaint letter",
    "draft_body": "complaint letter",
}


# ── Events and status ───────────────────────────────────────────────────────


def record_event(
    db: Session,
    complaint: Complaint,
    event_type: EventType,
    description: str,
    *,
    actor: Actor = Actor.CITIZEN,
    previous_status: ComplaintStatus | None = None,
    new_status: ComplaintStatus | None = None,
    details: dict[str, Any] | None = None,
) -> ComplaintEvent:
    """Add an event to the complaint's timeline. The caller commits."""
    event = ComplaintEvent(
        complaint_id=complaint.id,
        event_type=event_type.value,
        description=description,
        actor=actor.value,
        previous_status=previous_status.value if previous_status else None,
        new_status=new_status.value if new_status else None,
        details=details or {},
    )
    db.add(event)
    complaint.updated_at = utc_now()  # any activity makes the complaint "recently updated"
    return event


def change_status(
    db: Session,
    complaint: Complaint,
    new_status: ComplaintStatus,
    *,
    event_type: EventType,
    description: str,
    actor: Actor = Actor.CITIZEN,
) -> None:
    """The ONLY way to change a complaint's status: validates the transition and records it."""
    current = ComplaintStatus(complaint.status)
    ensure_transition(current, new_status)
    complaint.status = new_status.value
    record_event(
        db,
        complaint,
        event_type,
        description,
        actor=actor,
        previous_status=current,
        new_status=new_status,
    )


def available_actions(complaint: Complaint) -> list[ComplaintAction]:
    """What the citizen can do next. The frontend shows buttons based on this list."""
    status = ComplaintStatus(complaint.status)
    actions: list[ComplaintAction] = []
    if status in EDITABLE_STATUSES:
        actions.append("edit")
        originals = [e for e in complaint.evidence if e.evidence_type == "ORIGINAL"]
        if len(originals) < MAX_ORIGINAL_PHOTOS:
            actions.append("add_photo")
    if status in EDITABLE_STATUSES and ready_to_submit(complaint):
        actions.append("submit")
    if status in VERIFIABLE_STATUSES:
        actions.append("verify")  # add an "after" photo, confirm or dispute the repair
    if status in (ComplaintStatus.CLOSED, ComplaintStatus.VERIFIED_RESOLVED):
        actions.append("reopen")  # the problem came back
    if can_transition(status, ComplaintStatus.CANCELLED):
        actions.append("cancel")
    if can_transition(status, ComplaintStatus.CLOSED):
        actions.append("close")
    return actions


def missing_for_submission(complaint: Complaint) -> list[str]:
    """What still has to be done before the complaint can be approved and sent."""
    checks = [
        ("a photo", any(e.evidence_type == "ORIGINAL" for e in complaint.evidence)),
        ("a title", complaint.title),
        ("a description", complaint.description),
        ("the type of issue", complaint.category),
        ("a confirmed location", complaint.location_confirmed_at),
        ("a department", complaint.authority and complaint.authority.official_email),
        ("a complaint letter", complaint.draft_subject and complaint.draft_body),
    ]
    return [label for label, present in checks if not present]


def ready_to_submit(complaint: Complaint) -> bool:
    return not missing_for_submission(complaint)


def withdraw_approval(db: Session, complaint: Complaint, reason: str) -> None:
    """An approved complaint that changes must be approved again before it can be sent."""
    if complaint.status == ComplaintStatus.PENDING_REVIEW.value:
        change_status(
            db,
            complaint,
            ComplaintStatus.DRAFT,
            event_type=EventType.APPROVAL_WITHDRAWN,
            description=f"Approval withdrawn because {reason}. Please review and approve again.",
            actor=Actor.SYSTEM,
        )


# ── Reading ─────────────────────────────────────────────────────────────────


def get_owned_complaint(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    """Load a complaint that belongs to `user`. Someone else's complaint gives the same 404 as a
    missing one, so IDs can't be probed."""
    complaint = db.scalar(
        select(Complaint)
        .where(Complaint.id == complaint_id, Complaint.user_id == user.id)
        .options(selectinload(Complaint.evidence), selectinload(Complaint.authority))
        # Reload even if this complaint is already in the session, so newly added
        # photos and changed fields are always included.
        .execution_options(populate_existing=True)
    )
    if complaint is None:
        raise NotFoundError("Complaint not found.")
    return complaint


def get_editable_complaint(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    complaint = get_owned_complaint(db, user, complaint_id)
    if ComplaintStatus(complaint.status) not in EDITABLE_STATUSES:
        raise InvalidTransitionError("This complaint can no longer be edited.")
    return complaint


def to_read(complaint: Complaint) -> ComplaintRead:
    read = ComplaintRead.model_validate(complaint)
    read.available_actions = available_actions(complaint)
    return read


def to_list_item(complaint: Complaint) -> ComplaintListItem:
    item = ComplaintListItem.model_validate(complaint)
    original = next((e for e in complaint.evidence if e.evidence_type == "ORIGINAL"), None)
    item.thumbnail_url = f"/api/v1/evidence/{original.id}/file" if original else None
    return item


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_complaints(
    db: Session, user: User, params: ComplaintListParams
) -> tuple[list[Complaint], int]:
    query = select(Complaint).where(Complaint.user_id == user.id)

    if params.search:
        pattern = f"%{_escape_like(params.search.strip())}%"
        query = query.where(
            or_(
                *(
                    column.ilike(pattern, escape="\\")
                    for column in (
                        Complaint.title,
                        Complaint.description,
                        Complaint.public_reference,
                        Complaint.address_line,
                        Complaint.locality,
                        Complaint.city,
                    )
                )
            )
        )
    if params.category:
        query = query.where(Complaint.category == params.category.value)
    if params.status:
        query = query.where(Complaint.status == params.status.value)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # public_reference comes from a sequence, so it breaks ties between equal timestamps
    # in creation order.
    order = {
        "-created_at": (Complaint.created_at.desc(), Complaint.public_reference.desc()),
        "created_at": (Complaint.created_at.asc(), Complaint.public_reference.asc()),
        "-updated_at": (Complaint.updated_at.desc(), Complaint.public_reference.desc()),
    }[params.sort]
    rows = db.scalars(
        query.options(selectinload(Complaint.evidence))
        .order_by(*order)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return list(rows), total


def get_timeline(db: Session, complaint: Complaint) -> list[ComplaintEvent]:
    return list(
        db.scalars(
            select(ComplaintEvent)
            .where(ComplaintEvent.complaint_id == complaint.id)
            .order_by(ComplaintEvent.created_at, ComplaintEvent.seq)
        ).all()
    )


# ── Writing ─────────────────────────────────────────────────────────────────


def _next_public_reference(db: Session) -> str:
    number = db.scalar(select(complaint_reference_seq.next_value()))
    return f"CP-{utc_now().year}-{number:06d}"


def create_complaint(db: Session, user: User, data: ComplaintCreate) -> Complaint:
    complaint = Complaint(
        user_id=user.id,
        public_reference=_next_public_reference(db),
        status=ComplaintStatus.DRAFT.value,
        **_column_values(data.model_dump(exclude_unset=True)),
    )
    db.add(complaint)
    db.flush()  # assigns the id so the event can reference it
    record_event(db, complaint, EventType.COMPLAINT_CREATED, "Complaint draft created.")
    db.commit()
    return get_owned_complaint(db, user, complaint.id)


def update_complaint(
    db: Session, user: User, complaint: Complaint, data: ComplaintUpdate
) -> Complaint:
    if ComplaintStatus(complaint.status) not in EDITABLE_STATUSES:
        raise InvalidTransitionError("This complaint can no longer be edited.")

    changes = _column_values(data.model_dump(exclude_unset=True, exclude={"confirm_location"}))

    # Check business rules BEFORE touching the complaint, so a rejected request changes nothing.
    if data.confirm_location:
        address_line = changes.get("address_line", complaint.address_line)
        city = changes.get("city", complaint.city)
        if not address_line or not city:
            raise BusinessRuleError(
                "Add at least an address and a city before confirming the location."
            )

    changed_fields = [
        name for name, value in changes.items() if not _same_value(getattr(complaint, name), value)
    ]
    for name, value in changes.items():
        setattr(complaint, name, value)

    if complaint.location_confirmed_at and _LOCATION_FIELDS & set(changed_fields):
        complaint.location_confirmed_at = None  # an edited location must be confirmed again

    # A department that doesn't handle the new issue type can't stay selected.
    department_cleared = False
    if (
        "category" in changed_fields
        and complaint.authority is not None
        and complaint.category not in complaint.authority.supported_categories
    ):
        complaint.authority_id = None
        department_cleared = True

    if changed_fields:
        labels = sorted({_FIELD_LABELS[name] for name in changed_fields})
        record_event(
            db,
            complaint,
            EventType.DETAILS_UPDATED,
            f"Updated {', '.join(labels)}."
            + (
                " The department was cleared: it doesn't handle this issue type."
                if department_cleared
                else ""
            ),
            details={"fields": changed_fields},
        )
        withdraw_approval(db, complaint, "the complaint was edited")

    if data.confirm_location:
        complaint.location_confirmed_at = utc_now()
        where = ", ".join(p for p in (complaint.locality, complaint.city) if p)
        record_event(db, complaint, EventType.LOCATION_CONFIRMED, f"Location confirmed: {where}.")

    db.commit()
    return get_owned_complaint(db, user, complaint.id)


def _stop_monitoring(db: Session, complaint: Complaint, reason: str) -> None:
    # Imported here, not at the top: the monitoring module itself builds on this module.
    from app.modules.monitoring.service import stop_monitoring

    stop_monitoring(db, complaint, reason)


def cancel_complaint(db: Session, user: User, complaint: Complaint) -> Complaint:
    was_submitted = complaint.submitted_at is not None
    change_status(
        db,
        complaint,
        ComplaintStatus.CANCELLED,
        event_type=EventType.COMPLAINT_CANCELLED,
        description=(
            "You withdrew the complaint. The department is not notified automatically."
            if was_submitted
            else "Complaint cancelled by the citizen."
        ),
    )
    _stop_monitoring(db, complaint, "you withdrew the complaint")
    db.commit()
    return get_owned_complaint(db, user, complaint.id)


def close_complaint(db: Session, user: User, complaint: Complaint) -> Complaint:
    change_status(
        db,
        complaint,
        ComplaintStatus.CLOSED,
        event_type=EventType.COMPLAINT_CLOSED,
        description="Complaint closed by the citizen.",
    )
    _stop_monitoring(db, complaint, "you closed the complaint")
    db.commit()
    return get_owned_complaint(db, user, complaint.id)


def _column_values(values: dict[str, Any]) -> dict[str, Any]:
    """Convert enum members to their plain string values for the VARCHAR columns."""
    return {k: (v.value if hasattr(v, "value") else v) for k, v in values.items()}


def _same_value(old: Any, new: Any) -> bool:
    # Coordinates come back from the database as Decimal; compare them as numbers.
    if isinstance(old, Decimal) and new is not None:
        return float(old) == float(new)
    return old == new


# ── Dashboard ───────────────────────────────────────────────────────────────


def dashboard_summary(db: Session, user: User) -> DashboardSummary:
    def count(*conditions: Any) -> int:
        query = select(func.count(Complaint.id)).where(Complaint.user_id == user.id, *conditions)
        return db.scalar(query) or 0

    verified_event = exists().where(
        ComplaintEvent.complaint_id == Complaint.id,
        ComplaintEvent.new_status == ComplaintStatus.VERIFIED_RESOLVED.value,
    )
    stats = DashboardStats(
        total=count(Complaint.status != ComplaintStatus.CANCELLED.value),
        drafts=count(Complaint.status.in_([s.value for s in EDITABLE_STATUSES])),
        active=count(Complaint.status.in_([s.value for s in ACTIVE_STATUSES])),
        pending_responses=count(Complaint.status == ComplaintStatus.SUBMITTED.value),
        # Verified now, or closed after the citizen had verified the fix.
        verified_resolutions=count(
            or_(
                Complaint.status == ComplaintStatus.VERIFIED_RESOLVED.value,
                (Complaint.status == ComplaintStatus.CLOSED.value) & verified_event,
            )
        ),
    )

    recent = db.scalars(
        select(Complaint)
        .where(Complaint.user_id == user.id)
        .options(selectinload(Complaint.evidence))
        .order_by(Complaint.updated_at.desc(), Complaint.public_reference.desc())
        .limit(5)
    ).all()

    activity_rows = db.execute(
        select(ComplaintEvent, Complaint.public_reference, Complaint.title)
        .join(Complaint, ComplaintEvent.complaint_id == Complaint.id)
        .where(Complaint.user_id == user.id)
        .order_by(ComplaintEvent.created_at.desc(), ComplaintEvent.seq.desc())
        .limit(8)
    ).all()
    activity = [
        ActivityItem(
            **ComplaintEventRead.model_validate(event).model_dump(),
            complaint_id=event.complaint_id,
            complaint_reference=reference,
            complaint_title=title,
        )
        for event, reference, title in activity_rows
    ]

    from app.modules.monitoring.service import attention_items  # see _stop_monitoring

    return DashboardSummary(
        stats=stats,
        recent_complaints=[to_list_item(c) for c in recent],
        recent_activity=activity,
        needs_attention=attention_items(db, user),
    )
