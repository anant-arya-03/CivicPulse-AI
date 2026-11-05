"""Complaint submission: preview → explicit approval → idempotent send.

Guarantees (each one is tested):
1. Nothing is sent without approval of the EXACT content: the approval stores a SHA-256 of the
   recipient, subject, body, and attachments the citizen saw. Any later change withdraws it.
2. A message is sent at most once: the database row is locked while sending, a sent message is
   never re-sent (repeat calls just return it), and the provider gets an idempotency key.
3. A failed send delivers nothing and can be retried safely.
4. Simulated sends are always recorded and shown as simulated, never as delivered.
5. Real (non-simulated) sending is refused unless explicitly allowed, and never goes to demo
   departments or reserved .example addresses.
6. Follow-up reminders (Milestone 5) use the same cycle: the worker only drafts them; the
   citizen edits, approves the exact content, and sends. The anti-spam rules are checked again
   at approval and at sending time (monitoring/rules.followup_blocker).
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    RealSubmissionBlockedError,
    SubmissionFailedError,
)
from app.integrations.email_providers.base import EmailProvider, EmailProviderError, OutgoingEmail
from app.modules.authorities.schemas import AuthorityRead
from app.modules.communications.hashing import content_sha256, message_sha256
from app.modules.communications.models import Communication
from app.modules.communications.schemas import (
    CommunicationRead,
    FollowupUpdate,
    PreviewAttachment,
    SubmissionPreview,
)
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import (
    EDITABLE_STATUSES,
    Actor,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint
from app.modules.monitoring import rules as monitoring_rules
from app.modules.monitoring import service as monitoring
from app.modules.monitoring.constants import CheckTrigger
from app.modules.users.models import User

logger = logging.getLogger(__name__)

_RESERVED_TLDS = {"example", "test", "invalid", "localhost"}
_STUCK_SENDING_AFTER = timedelta(minutes=10)


def _photos(complaint: Complaint) -> list[dict[str, str]]:
    return [
        {"evidence_id": str(e.id), "file_type": e.file_type}
        for e in complaint.evidence
        if e.evidence_type == "ORIGINAL"
    ]


def content_hash(complaint: Complaint) -> str | None:
    """Fingerprint of exactly what would be sent; changes if anything approved changes."""
    if not complaint.authority or not complaint.draft_subject or not complaint.draft_body:
        return None
    return content_sha256(
        to=complaint.authority.official_email,
        subject=complaint.draft_subject,
        body=complaint.draft_body,
        attachment_ids=(p["evidence_id"] for p in _photos(complaint)),
    )


def _complaint_messages(db: Session, complaint: Complaint) -> list[Communication]:
    return list(
        db.scalars(
            select(Communication)
            .where(
                Communication.complaint_id == complaint.id,
                Communication.communication_type == "COMPLAINT",
            )
            .order_by(Communication.seq)
        ).all()
    )


def _pending(db: Session, complaint: Complaint) -> Communication | None:
    """An approved (or failed) complaint message that hasn't been sent yet."""
    return next(
        (
            m
            for m in reversed(_complaint_messages(db, complaint))
            if m.delivery_status in ("APPROVED", "FAILED", "SENDING")
        ),
        None,
    )


# ── Preview ─────────────────────────────────────────────────────────────────


def preview(
    db: Session, provider: EmailProvider, user: User, complaint_id: uuid.UUID
) -> SubmissionPreview:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    missing = complaint_service.missing_for_submission(complaint)
    pending = (
        _pending(db, complaint) if complaint.status == ComplaintStatus.PENDING_REVIEW else None
    )
    return SubmissionPreview(
        ready=not missing and ComplaintStatus(complaint.status) in EDITABLE_STATUSES,
        missing=missing,
        authority=AuthorityRead.model_validate(complaint.authority)
        if complaint.authority
        else None,
        recipient=complaint.authority.official_email if complaint.authority else None,
        from_address=get_settings().email_from_address,
        subject=complaint.draft_subject,
        body=complaint.draft_body,
        attachments=[
            PreviewAttachment(
                evidence_id=uuid.UUID(p["evidence_id"]),
                url=f"/api/v1/evidence/{p['evidence_id']}/file",
                file_type=p["file_type"],
            )
            for p in _photos(complaint)
        ],
        is_simulated=provider.is_simulated,
        content_sha256=content_hash(complaint),
        pending_communication=CommunicationRead.model_validate(pending) if pending else None,
    )


# ── Approval ────────────────────────────────────────────────────────────────


def approve(
    db: Session, provider: EmailProvider, user: User, complaint_id: uuid.UUID, seen_hash: str
) -> Communication:
    complaint = complaint_service.get_editable_complaint(db, user, complaint_id)
    missing = complaint_service.missing_for_submission(complaint)
    if missing:
        raise BusinessRuleError(f"Before approving, add {', '.join(missing)}.")

    current_hash = content_hash(complaint)
    if seen_hash != current_hash:
        raise ConflictError(
            "The complaint changed after you opened the preview. Please review it again."
        )

    pending = _pending(db, complaint)
    if (
        complaint.status == ComplaintStatus.PENDING_REVIEW.value
        and pending is not None
        and pending.content_sha256 == current_hash
    ):
        return pending  # already approved exactly this content

    for old in _complaint_messages(db, complaint):
        if old.delivery_status in ("APPROVED", "FAILED"):
            old.delivery_status = "SUPERSEDED"  # an older approval can never be sent now

    authority = complaint.authority
    assert authority is not None and authority.official_email is not None  # checked above
    version = len(_complaint_messages(db, complaint)) + 1
    now = utc_now()
    message = Communication(
        complaint_id=complaint.id,
        authority_id=authority.id,
        direction="OUTBOUND",
        communication_type="COMPLAINT",
        channel="EMAIL",
        recipient=authority.official_email,
        sender=get_settings().email_from_address,
        subject=complaint.draft_subject,
        body=complaint.draft_body,
        attachments=_photos(complaint),
        delivery_status="APPROVED",
        is_simulated=provider.is_simulated,
        provider=provider.name,
        idempotency_key=f"complaint:{complaint.id}:v{version}",
        content_sha256=current_hash,
        approval_details={
            "approved_by": str(user.id),
            "approved_at": now.isoformat(),
            "content_sha256": current_hash,
            "recipient": authority.official_email,
        },
    )
    db.add(message)
    db.flush()

    if complaint.status == ComplaintStatus.DRAFT.value:
        complaint_service.change_status(
            db,
            complaint,
            ComplaintStatus.PENDING_REVIEW,
            event_type=EventType.COMPLAINT_APPROVED,
            description=f"You approved the complaint for sending to {authority.name}.",
        )
    else:  # already PENDING_REVIEW (e.g. re-approving after a change): just record it
        complaint_service.record_event(
            db,
            complaint,
            EventType.COMPLAINT_APPROVED,
            f"You approved the complaint for sending to {authority.name}.",
        )
    db.commit()
    return message


# ── Sending ─────────────────────────────────────────────────────────────────


def _check_real_send_allowed(
    provider: EmailProvider, message: Communication, complaint: Complaint
) -> None:
    """Safety net for a future real provider. The simulated provider never reaches anyone."""
    if provider.is_simulated:
        return
    recipient = (message.recipient or "").lower()
    tld = recipient.rsplit("@", 1)[-1].rsplit(".", 1)[-1]
    if not get_settings().allow_real_submissions:
        raise RealSubmissionBlockedError(
            "Real submissions are switched off (ALLOW_REAL_SUBMISSIONS)."
        )
    if complaint.authority is None or complaint.authority.is_demo or tld in _RESERVED_TLDS:
        raise RealSubmissionBlockedError("Refusing to send a real email to a demo department.")


def _owned_message(
    db: Session, user: User, communication_id: uuid.UUID, *, lock: bool = False
) -> Communication:
    query = (
        select(Communication)
        .join(Complaint, Communication.complaint_id == Complaint.id)
        .where(Communication.id == communication_id, Complaint.user_id == user.id)
    )
    if lock:
        # A second, simultaneous request waits here and then sees what the first one did.
        query = query.with_for_update(of=Communication)
    message = db.scalar(query)
    if message is None:
        raise NotFoundError("Message not found.")
    return message


def _check_complaint_sendable(complaint: Complaint, message: Communication) -> None:
    if complaint.status != ComplaintStatus.PENDING_REVIEW.value:
        raise InvalidTransitionError("This complaint isn't approved for sending.")
    if content_hash(complaint) != message.content_sha256:
        raise ConflictError("The complaint changed after you approved it. Please approve it again.")


def _followup_name(message: Communication) -> str:
    """ "reminder 2", or "the 'not fixed' message" for a notice after a disputed repair."""
    if message.followup_number is None:
        return "the 'not fixed' message"
    return f"reminder {message.followup_number}"


def _reminders_sent(db: Session, complaint: Complaint, message: Communication) -> int:
    # A "not fixed" notice is the citizen's answer to a claimed repair: the limit on
    # repeated reminders doesn't apply to it.
    return 0 if message.followup_number is None else monitoring.sent_followup_count(db, complaint)


def _check_followup_sendable(db: Session, complaint: Complaint, message: Communication) -> None:
    blocker = monitoring_rules.followup_blocker(
        status=ComplaintStatus(complaint.status),
        sent_count=_reminders_sent(db, complaint, message),
        max_count=get_settings().followup_max_count,
        has_open_followup=False,  # this message IS the open reminder
    )
    if blocker:
        raise ConflictError(f"This reminder can't be sent. {blocker}")
    if message_sha256(message) != message.content_sha256:
        raise ConflictError("The reminder changed after you approved it. Please approve it again.")


def send(
    db: Session, provider: EmailProvider, user: User, communication_id: uuid.UUID
) -> Communication:
    message = _owned_message(db, user, communication_id, lock=True)
    is_followup = message.communication_type == "FOLLOW_UP"
    what = "reminder" if is_followup else "complaint"

    if message.delivery_status in ("SENT", "SIMULATED_SENT"):
        db.rollback()
        return message  # already sent: never send twice
    if message.delivery_status in ("SUPERSEDED", "CANCELLED"):
        db.rollback()
        raise ConflictError(f"This {what} was replaced or cancelled and can't be sent.")
    stale = message.updated_at < utc_now() - _STUCK_SENDING_AFTER
    if message.delivery_status == "SENDING" and not stale:
        db.rollback()
        raise ConflictError(f"This {what} is already being sent. Please wait a moment.")
    if message.direction != "OUTBOUND" or message.delivery_status not in (
        "APPROVED",
        "FAILED",
        "SENDING",
    ):
        db.rollback()
        raise ConflictError(f"Please approve the {what} before sending it.")

    complaint = complaint_service.get_owned_complaint(db, user, message.complaint_id)
    try:
        if is_followup:
            _check_followup_sendable(db, complaint, message)
        else:
            _check_complaint_sendable(complaint, message)
        _check_real_send_allowed(provider, message, complaint)
    except Exception:
        db.rollback()  # release the row lock before reporting the problem
        raise

    message.delivery_status = "SENDING"
    message.attempt_count += 1
    attempt = message.attempt_count
    action_text = f"Sending {_followup_name(message)}" if is_followup else "Sending the complaint"
    complaint_service.record_event(
        db,
        complaint,
        EventType.SUBMISSION_ATTEMPTED,
        f"{action_text} (simulation)…" if provider.is_simulated else f"{action_text}…",
        actor=Actor.SYSTEM,
        details={"communication_id": str(message.id), "attempt": attempt},
    )
    db.commit()  # releases the lock; the SENDING status keeps others out

    email = OutgoingEmail(
        to=message.recipient or "",
        subject=message.subject,
        body=message.body,
        from_address=message.sender or get_settings().email_from_address,
        idempotency_key=message.idempotency_key or str(message.id),
        attachment_names=[f"photo-{i + 1}" for i in range(len(message.attachments))],
    )
    try:
        result = provider.send(email)
    except EmailProviderError as error:
        logger.warning("Sending communication %s failed: %s", message.id, error)
        message.delivery_status = "FAILED"
        message.error_message = str(error)[:500]
        complaint_service.record_event(
            db,
            complaint,
            EventType.FOLLOWUP_FAILED if is_followup else EventType.SUBMISSION_FAILED,
            f"Sending the {what} failed. Nothing was delivered. You can try again.",
            actor=Actor.SYSTEM,
            details={"communication_id": str(message.id), "attempt": attempt},
        )
        db.commit()
        raise SubmissionFailedError(
            f"Sending the {what} failed and nothing was delivered. Please try again.",
            {"communication_id": str(message.id)},
        ) from error

    now = utc_now()
    message.delivery_status = "SIMULATED_SENT" if provider.is_simulated else "SENT"
    message.provider_message_id = result.provider_message_id
    message.sent_at = now
    message.error_message = None
    authority_name = complaint.authority.name if complaint.authority else "the department"
    simulated_note = " No email was sent to a real department." if provider.is_simulated else ""
    if is_followup:
        complaint_service.record_event(
            db,
            complaint,
            EventType.FOLLOWUP_SENT,
            ("Simulated: " if provider.is_simulated else "")
            + f"{_followup_name(message).capitalize()} sent to {authority_name}.{simulated_note}",
            actor=Actor.SYSTEM,
            details={"communication_id": str(message.id)},
        )
        monitoring.schedule_check(db, complaint, CheckTrigger.FOLLOWUP_SENT, at=now, after=message)
    else:
        complaint.submitted_at = now
        complaint_service.change_status(
            db,
            complaint,
            ComplaintStatus.SUBMITTED,
            event_type=EventType.SUBMISSION_ACCEPTED,
            description=(
                f"Simulated submission to {authority_name}.{simulated_note}"
                if provider.is_simulated
                else f"Complaint sent to {authority_name}."
            ),
            actor=Actor.SYSTEM,
        )
        monitoring.schedule_check(db, complaint, CheckTrigger.COMPLAINT_SENT, at=now, after=message)
    db.commit()
    return message


# ── Follow-up reminders: edit → approve → send (or dismiss) ─────────────────


def _owned_followup(
    db: Session, user: User, communication_id: uuid.UUID
) -> tuple[Communication, Complaint]:
    message = _owned_message(db, user, communication_id, lock=True)
    if message.communication_type != "FOLLOW_UP":
        raise ConflictError("Only reminders can be changed this way.")
    complaint = complaint_service.get_owned_complaint(db, user, message.complaint_id)
    return message, complaint


def update_followup(
    db: Session, user: User, communication_id: uuid.UUID, data: FollowupUpdate
) -> Communication:
    message, complaint = _owned_followup(db, user, communication_id)
    if message.delivery_status not in ("DRAFT", "APPROVED", "FAILED"):
        raise ConflictError("This reminder can't be edited any more.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    changed = {k: v for k, v in changes.items() if getattr(message, k) != v}
    if not changed:
        return message
    for field, value in changed.items():
        setattr(message, field, value)
    was_approved = message.delivery_status != "DRAFT"
    # A changed reminder needs a new approval: the old one was for different words.
    message.delivery_status = "DRAFT"
    message.content_sha256 = None
    message.approval_details = None
    complaint_service.record_event(
        db,
        complaint,
        EventType.DETAILS_UPDATED,
        f"You edited {_followup_name(message)}."
        + (" Please approve it again." if was_approved else ""),
    )
    db.commit()
    return message


def approve_followup(
    db: Session, provider: EmailProvider, user: User, communication_id: uuid.UUID, seen_hash: str
) -> Communication:
    message, complaint = _owned_followup(db, user, communication_id)
    current_hash = message_sha256(message)
    if message.delivery_status == "APPROVED" and message.content_sha256 == current_hash:
        db.rollback()
        return message  # already approved exactly this content
    if message.delivery_status != "DRAFT":
        raise ConflictError("This reminder can't be approved any more.")
    if seen_hash != current_hash:
        raise ConflictError("The reminder changed after you opened it. Please review it again.")
    blocker = monitoring_rules.followup_blocker(
        status=ComplaintStatus(complaint.status),
        sent_count=_reminders_sent(db, complaint, message),
        max_count=get_settings().followup_max_count,
        has_open_followup=False,  # this message IS the open reminder
    )
    if blocker:
        raise ConflictError(blocker)

    message.delivery_status = "APPROVED"
    message.content_sha256 = current_hash
    message.is_simulated = provider.is_simulated
    message.provider = provider.name
    message.approval_details = {
        "approved_by": str(user.id),
        "approved_at": utc_now().isoformat(),
        "content_sha256": current_hash,
        "recipient": message.recipient,
    }
    authority_name = complaint.authority.name if complaint.authority else "the department"
    complaint_service.record_event(
        db,
        complaint,
        EventType.FOLLOWUP_APPROVED,
        f"You approved {_followup_name(message)} for sending to {authority_name}.",
        details={"communication_id": str(message.id)},
    )
    db.commit()
    return message


def dismiss_followup(db: Session, user: User, communication_id: uuid.UUID) -> Communication:
    """The citizen decides not to send this reminder. We check again after one interval."""
    message, complaint = _owned_followup(db, user, communication_id)
    if message.delivery_status == "CANCELLED":
        db.rollback()
        return message
    if message.delivery_status not in ("DRAFT", "APPROVED", "FAILED"):
        raise ConflictError("This reminder can't be dismissed any more.")
    message.delivery_status = "CANCELLED"
    check = monitoring.schedule_check(
        db, complaint, CheckTrigger.FOLLOWUP_DISMISSED, at=utc_now(), after=message
    )
    next_check = f" We'll check again on {check.scheduled_at:%d %B %Y}." if check else ""
    complaint_service.record_event(
        db,
        complaint,
        EventType.FOLLOWUP_DISMISSED,
        f"You chose not to send {_followup_name(message)}.{next_check}",
        details={"communication_id": str(message.id)},
    )
    db.commit()
    return message


def list_communications(db: Session, user: User, complaint_id: uuid.UUID) -> list[Communication]:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    return list(
        db.scalars(
            select(Communication)
            .where(Communication.complaint_id == complaint.id)
            .order_by(Communication.seq)
        ).all()
    )
