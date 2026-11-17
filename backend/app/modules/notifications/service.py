"""Owner-scoped notifications derived from the existing audit trail."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.complaints.models import Complaint, ComplaintEvent
from app.modules.users.models import User


def event_types(user: User) -> list[str]:
    preferences = user.notification_preferences or {}
    kinds = []
    if preferences.get("followup_ready", True):
        kinds += ["FOLLOWUP_SUGGESTED", "FOLLOWUP_FAILED", "ESCALATION_RECOMMENDED"]
    if preferences.get("status_changes", True):
        kinds += ["REPLY_RECEIVED", "STATUS_CHANGED", "RESOLUTION_CONFIRMED", "RESOLUTION_DISPUTED"]
    return kinds


def query(user: User):
    return (
        select(ComplaintEvent)
        .join(Complaint)
        .where(Complaint.user_id == user.id, ComplaintEvent.event_type.in_(event_types(user)))
    )


def list_notifications(db: Session, user: User) -> dict:
    events = db.scalars(query(user).order_by(ComplaintEvent.seq.desc()).limit(30)).all()
    unread = db.scalar(
        select(func.count()).select_from(
            query(user).where(ComplaintEvent.seq > user.notifications_last_seen_seq).subquery()
        )
    )
    return {
        "unread_count": unread,
        "items": [
            {
                "id": str(e.id),
                "complaint_id": str(e.complaint_id),
                "description": e.description,
                "created_at": e.created_at,
                "unread": e.seq > user.notifications_last_seen_seq,
            }
            for e in events
        ],
    }


def mark_seen(db: Session, user: User, event_id) -> None:
    event = db.scalar(query(user).where(ComplaintEvent.id == event_id))
    if event is None:
        raise NotFoundError("Notification not found.")
    # A stale browser tab cannot move the cursor backwards. Lock before reading it.
    locked = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked.notifications_last_seen_seq = max(locked.notifications_last_seen_seq, event.seq)
    db.commit()
