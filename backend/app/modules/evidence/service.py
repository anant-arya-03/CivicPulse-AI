"""Evidence (photo) business logic: upload, ownership checks, serving, and removal."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, InvalidTransitionError, NotFoundError
from app.integrations.storage.base import StorageService
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import (
    EDITABLE_STATUSES,
    VERIFIABLE_STATUSES,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint
from app.modules.evidence.image_validation import validate_and_clean_image
from app.modules.evidence.models import Evidence
from app.modules.users.models import User

logger = logging.getLogger(__name__)

ORIGINAL = "ORIGINAL"
FOLLOWUP = "FOLLOWUP"
MAX_FOLLOWUP_PHOTOS = 5


def upload_evidence(
    db: Session,
    storage: StorageService,
    user: User,
    complaint_id: uuid.UUID,
    raw: bytes,
) -> Evidence:
    """An original photo of the problem (while the complaint is a draft)."""
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    if ComplaintStatus(complaint.status) not in EDITABLE_STATUSES:
        raise InvalidTransitionError("Photos can only be added while the complaint is a draft.")
    originals = [e for e in complaint.evidence if e.evidence_type == ORIGINAL]
    if len(originals) >= complaint_service.MAX_ORIGINAL_PHOTOS:
        raise BusinessRuleError(
            f"A complaint can have at most {complaint_service.MAX_ORIGINAL_PHOTOS} photos."
        )
    return _store_photo(db, storage, complaint, raw, ORIGINAL, "Photo uploaded.")


def upload_followup_evidence(
    db: Session,
    storage: StorageService,
    user: User,
    complaint_id: uuid.UUID,
    raw: bytes,
) -> Evidence:
    """An "after" photo, to check whether the problem was fixed. Same validation and metadata
    stripping as the original photos."""
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    if ComplaintStatus(complaint.status) not in VERIFIABLE_STATUSES:
        raise InvalidTransitionError(
            "Follow-up photos can be added once the complaint has been sent, until it is closed."
        )
    followups = [e for e in complaint.evidence if e.evidence_type == FOLLOWUP]
    if len(followups) >= MAX_FOLLOWUP_PHOTOS:
        raise BusinessRuleError(
            f"A complaint can have at most {MAX_FOLLOWUP_PHOTOS} follow-up photos."
        )
    return _store_photo(
        db, storage, complaint, raw, FOLLOWUP, "Follow-up photo uploaded to check the repair."
    )


def _store_photo(
    db: Session,
    storage: StorageService,
    complaint: Complaint,
    raw: bytes,
    evidence_type: str,
    event_text: str,
) -> Evidence:
    image = validate_and_clean_image(raw, max_bytes=get_settings().max_upload_bytes)
    if any(e.checksum == image.checksum for e in complaint.evidence):
        raise ConflictError(
            "This photo is already attached to the complaint."
            if evidence_type == ORIGINAL
            else "This is the same photo as before. Please take a new photo of the place."
        )

    evidence_id = uuid.uuid4()
    key = f"complaints/{complaint.id}/{evidence_id}.{image.extension}"
    storage.save(key, image.data)
    try:
        evidence = Evidence(
            id=evidence_id,
            complaint_id=complaint.id,
            evidence_type=evidence_type,
            file_storage_key=key,
            file_type=image.mime_type,
            file_size_bytes=len(image.data),
            width=image.width,
            height=image.height,
            checksum=image.checksum,
        )
        db.add(evidence)
        complaint_service.record_event(
            db,
            complaint,
            EventType.EVIDENCE_UPLOADED
            if evidence_type == ORIGINAL
            else EventType.RESOLUTION_EVIDENCE_UPLOADED,
            event_text,
            details={"evidence_id": str(evidence_id)},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)  # don't leave an orphaned file behind
        raise
    return evidence


def get_owned_evidence(db: Session, user: User, evidence_id: uuid.UUID) -> Evidence:
    """Photos are as private as their complaint: someone else's photo is a 404."""
    evidence = db.scalar(
        select(Evidence)
        .join(Complaint, Evidence.complaint_id == Complaint.id)
        .where(Evidence.id == evidence_id, Complaint.user_id == user.id)
    )
    if evidence is None:
        raise NotFoundError("Photo not found.")
    return evidence


def read_evidence_file(storage: StorageService, evidence: Evidence) -> bytes:
    try:
        return storage.read(evidence.file_storage_key)
    except FileNotFoundError:
        logger.error("Evidence %s is missing its file %s", evidence.id, evidence.file_storage_key)
        raise NotFoundError("Photo file not found.") from None


def delete_evidence(
    db: Session, storage: StorageService, user: User, evidence_id: uuid.UUID
) -> None:
    evidence = get_owned_evidence(db, user, evidence_id)
    complaint = evidence.complaint
    if evidence.evidence_type != ORIGINAL or ComplaintStatus(complaint.status) not in (
        EDITABLE_STATUSES
    ):
        raise InvalidTransitionError("Photos can only be removed while the complaint is a draft.")

    key = evidence.file_storage_key
    db.delete(evidence)
    complaint_service.record_event(
        db,
        complaint,
        EventType.EVIDENCE_REMOVED,
        "Photo removed.",
        details={"evidence_id": str(evidence_id)},
    )
    db.commit()
    storage.delete(key)  # only after the database change is safely committed
