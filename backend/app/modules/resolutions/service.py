"""Checking a reported repair: an "after" photo, the AI's comparison (advice), and the
citizen's decision.

Guarantees (each one is tested):
1. Only the citizen's decision changes the status. The AI comparison is stored and shown as
   advice ("The AI thinks..."), with plain warnings when it is unsure (rules.cautions).
2. Decisions follow the status machine (rules.transitions_for): a repair can be disputed only
   after the department claimed it; confirming ends monitoring.
3. Each check is decided once. Repeating the same decision is harmless; a different one is
   refused. A newer photo supersedes an undecided older check. Nothing is deleted (audit trail).
4. An AI failure never blocks the citizen: they compare the photos themselves.
5. Disputing (or reopening) drafts a "not fixed" message for the department. It is only sent
   after the citizen approves it, like every other message.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
)
from app.integrations.ai_providers.base import AIProvider
from app.integrations.email_providers.base import EmailProvider
from app.integrations.storage.base import StorageService
from app.modules.ai import service as ai_service
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import (
    VERIFIABLE_STATUSES,
    Actor,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint
from app.modules.evidence.models import Evidence
from app.modules.evidence.schemas import EvidenceRead
from app.modules.monitoring import service as monitoring
from app.modules.resolutions import rules
from app.modules.resolutions.models import ResolutionReview
from app.modules.resolutions.schemas import ResolutionReviewRead
from app.modules.users.models import User

_ASSESSMENT_LABELS = {
    "APPEARS_RESOLVED": "appears repaired",
    "PARTIALLY_RESOLVED": "appears partly repaired",
    "NOT_RESOLVED": "the problem appears to still be there",
    "CANNOT_DETERMINE": "can't tell from these photos",
}


def _lock_complaint(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    """Lock the complaint row, so two decisions or reopen requests can't race each other."""
    locked = db.scalar(
        select(Complaint.id)
        .where(Complaint.id == complaint_id, Complaint.user_id == user.id)
        .with_for_update()
    )
    if locked is None:
        raise NotFoundError("Complaint not found.")
    return complaint_service.get_owned_complaint(db, user, complaint_id)


def _owned_review(db: Session, user: User, review_id: uuid.UUID) -> ResolutionReview:
    review = db.scalar(
        select(ResolutionReview)
        .join(Complaint, ResolutionReview.complaint_id == Complaint.id)
        .where(ResolutionReview.id == review_id, Complaint.user_id == user.id)
    )
    if review is None:
        raise NotFoundError("Check not found.")
    return review


def to_read(db: Session, review: ResolutionReview) -> ResolutionReviewRead:
    after = db.get(Evidence, review.followup_evidence_id)
    before = db.get(Evidence, review.original_evidence_id) if review.original_evidence_id else None
    assert after is not None  # the review is deleted with its photo
    return ResolutionReviewRead(
        id=review.id,
        complaint_id=review.complaint_id,
        followup_evidence=EvidenceRead.model_validate(after),
        original_evidence=EvidenceRead.model_validate(before) if before else None,
        ai_status=review.ai_status,  # type: ignore[arg-type]
        ai_error_code=review.ai_error_code,
        is_mock=review.is_mock,
        assessment=review.ai_assessment,
        cautions=rules.cautions(review.ai_assessment),
        decision=review.decision,  # type: ignore[arg-type]
        citizen_notes=review.citizen_notes,
        decided_at=review.decided_at,
        created_at=review.created_at,
    )


def list_reviews(db: Session, user: User, complaint_id: uuid.UUID) -> list[ResolutionReview]:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    return list(
        db.scalars(
            select(ResolutionReview)
            .where(ResolutionReview.complaint_id == complaint.id)
            .order_by(ResolutionReview.seq)
        ).all()
    )


# ── Comparing the photos ────────────────────────────────────────────────────


def create_review(
    db: Session,
    storage: StorageService,
    ai: AIProvider,
    user: User,
    complaint_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> ResolutionReview:
    """Compare an "after" photo with the original. Asking again for the same photo returns the
    same check, or retries the AI if it failed last time."""
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    if ComplaintStatus(complaint.status) not in VERIFIABLE_STATUSES:
        raise InvalidTransitionError(
            "A repair can be checked once the complaint has been sent, until it is closed."
        )
    after = next((e for e in complaint.evidence if e.id == evidence_id), None)
    if after is None:
        raise NotFoundError("Photo not found.")
    if after.evidence_type != "FOLLOWUP":
        raise BusinessRuleError("Choose a follow-up photo taken after the repair.")

    review = db.scalar(
        select(ResolutionReview).where(ResolutionReview.followup_evidence_id == after.id)
    )
    if review is not None and (review.ai_status == "SUCCEEDED" or review.decision != "PENDING"):
        return review

    before = next((e for e in complaint.evidence if e.evidence_type == "ORIGINAL"), None)
    if review is None:
        # A newer photo replaces an undecided older check (kept, marked SUPERSEDED).
        for old in db.scalars(
            select(ResolutionReview).where(
                ResolutionReview.complaint_id == complaint.id,
                ResolutionReview.decision == "PENDING",
            )
        ):
            old.decision = "SUPERSEDED"
        db.flush()  # before the insert: only one PENDING check per complaint is allowed
        review = ResolutionReview(
            complaint_id=complaint.id,
            followup_evidence_id=after.id,
            original_evidence_id=before.id if before else None,
            ai_status="FAILED",
            decision="PENDING",
        )
        db.add(review)

    if before is None:
        result, analysis, error_code = None, None, "NO_ORIGINAL_PHOTO"
    else:
        result, analysis, error_code = ai_service.compare_photos(
            db, storage, ai, complaint, before=before, after=after
        )

    if result is not None and analysis is not None:
        assessment = result.output
        review.ai_status = "SUCCEEDED"
        review.ai_error_code = None
        review.ai_assessment = assessment.model_dump(mode="json")
        review.ai_analysis_id = analysis.id
        review.is_mock = result.is_mock
        who = "Demo AI" if result.is_mock else "AI"
        complaint_service.record_event(
            db,
            complaint,
            EventType.RESOLUTION_ASSESSED,
            f"{who} compared the photos: {_ASSESSMENT_LABELS[assessment.assessment]}. "
            "This is advice only; you decide.",
            actor=Actor.AI,
            details={"analysis_id": str(analysis.id), "is_mock": result.is_mock},
        )
    else:
        review.ai_status = "FAILED"
        review.ai_error_code = error_code
    db.commit()
    return review


# ── The citizen's decision ──────────────────────────────────────────────────


def decide(
    db: Session,
    email: EmailProvider,
    user: User,
    review_id: uuid.UUID,
    decision: rules.Decision,
    notes: str | None,
) -> ResolutionReview:
    review = _owned_review(db, user, review_id)
    complaint = _lock_complaint(db, user, review.complaint_id)
    db.refresh(review)  # read it again now that we hold the lock
    if review.decision == decision:
        db.rollback()
        return review  # the same answer twice: nothing more to do
    if review.decision == "SUPERSEDED":
        raise ConflictError("A newer photo replaced this check. Please decide on the newest one.")
    if review.decision != "PENDING":
        raise ConflictError("You have already decided on this check.")

    steps = rules.transitions_for(decision, ComplaintStatus(complaint.status))
    if steps is None:
        raise InvalidTransitionError(
            "You can only dispute a repair after the department reports it as fixed."
            if decision == "DISPUTED"
            else "This complaint can't be confirmed as fixed at the moment."
        )
    notes = (notes or "").strip() or None

    if decision == "CONFIRMED_RESOLVED":
        monitoring.stop_monitoring(db, complaint, "you confirmed the issue is fixed")
        for target in steps:
            if target == ComplaintStatus.RESOLVED_PENDING_VERIFICATION:
                complaint_service.change_status(
                    db,
                    complaint,
                    target,
                    event_type=EventType.STATUS_CHANGED,
                    description="You reported that the issue looks fixed.",
                )
            else:
                complaint_service.change_status(
                    db,
                    complaint,
                    target,
                    event_type=EventType.RESOLUTION_CONFIRMED,
                    description="You checked the place and confirmed the issue is fixed.",
                )
    else:
        complaint_service.change_status(
            db,
            complaint,
            ComplaintStatus.REOPENED,
            event_type=EventType.RESOLUTION_DISPUTED,
            description=(
                "You checked the place and found the issue is not fixed. The complaint is reopened."
            ),
        )
        monitoring.draft_not_fixed_notice(
            db,
            complaint,
            email=email,
            key=f"notice:review:{review.id}",
            came_back=False,
            notes=notes,
        )

    review.decision = decision
    review.citizen_notes = notes
    review.decided_at = utc_now()
    review.decided_by = user.id
    db.commit()
    return review


def reopen(
    db: Session, email: EmailProvider, user: User, complaint_id: uuid.UUID, notes: str | None
) -> Complaint:
    """The problem came back after the complaint was verified or closed."""
    complaint = _lock_complaint(db, user, complaint_id)
    if complaint.status not in (
        ComplaintStatus.CLOSED.value,
        ComplaintStatus.VERIFIED_RESOLVED.value,
    ):
        raise InvalidTransitionError("Only a verified or closed complaint can be reopened.")
    notes = (notes or "").strip() or None
    complaint_service.change_status(
        db,
        complaint,
        ComplaintStatus.REOPENED,
        event_type=EventType.COMPLAINT_REOPENED,
        description="You reopened the complaint because the problem came back.",
    )
    monitoring.draft_not_fixed_notice(
        db,
        complaint,
        email=email,
        key=f"notice:reopen:{complaint.id}:{uuid.uuid4()}",
        came_back=True,
        notes=notes,
    )
    db.commit()
    return complaint_service.get_owned_complaint(db, user, complaint.id)
