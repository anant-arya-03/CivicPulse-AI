"""AI business logic: run the agents, record every call, and keep humans in control.

Rules this file enforces:
- AI output never changes a complaint's details. Vision results are only *suggestions*; the
  frontend applies them to fields the citizen left empty.
- A complaint letter the citizen already has is never replaced unless they ask for it.
- Every call is stored in ai_analyses (provider, model, prompt version, timing, outcome), and
  the complaint's timeline shows it.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    AIUnavailableError,
    BusinessRuleError,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
)
from app.integrations.ai_providers.base import AIProvider, AIProviderError, AIResult
from app.integrations.storage.base import StorageService
from app.modules.ai.agents import (
    complaint_writer_agent,
    monitoring_agent,
    resolution_agent,
    vision_agent,
)
from app.modules.ai.followup_template import template_followup_prose
from app.modules.ai.image_prep import prepare_for_model
from app.modules.ai.letter_template import build_facts, render_letter, template_prose
from app.modules.ai.models import AIAnalysis
from app.modules.ai.schemas import (
    ComplaintDraftRequest,
    ComplaintDraftResponse,
    FollowupProse,
    ReplyClassification,
    ResolutionAssessment,
)
from app.modules.communications.models import Communication
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import (
    CATEGORY_LABELS,
    EDITABLE_STATUSES,
    Actor,
    Category,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint
from app.modules.evidence.models import Evidence
from app.modules.evidence.service import read_evidence_file
from app.modules.users.models import User

logger = logging.getLogger(__name__)

VISION = "VISION"
COMPLAINT_DRAFT = "COMPLAINT_DRAFT"
REPLY_CLASSIFICATION = "REPLY_CLASSIFICATION"
FOLLOWUP_DRAFT = "FOLLOWUP_DRAFT"
RESOLUTION = "RESOLUTION"

_FAILURE_TEXT = {
    VISION: "AI photo analysis was unavailable.",
    COMPLAINT_DRAFT: "AI letter drafting was unavailable.",
    REPLY_CLASSIFICATION: "AI couldn't read the reply. Please tell us what it means.",
    FOLLOWUP_DRAFT: "AI reminder drafting was unavailable, so the standard wording was used.",
    RESOLUTION: "AI photo comparison was unavailable. Please compare the photos yourself.",
}

_VISION_UNAVAILABLE = "AI analysis isn't available right now. You can fill in the details yourself."
_LETTER_UNAVAILABLE = (
    "The AI couldn't write the letter right now. You can start from a basic template instead."
)


def _editable_complaint(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    if ComplaintStatus(complaint.status) not in EDITABLE_STATUSES:
        raise InvalidTransitionError("AI help is only available while the complaint is a draft.")
    return complaint


def _record_success(
    db: Session,
    complaint: Complaint,
    analysis_type: str,
    prompt_version: str,
    result: AIResult,
    evidence_id: uuid.UUID | None = None,
    communication_id: uuid.UUID | None = None,
) -> AIAnalysis:
    analysis = AIAnalysis(
        complaint_id=complaint.id,
        analysis_type=analysis_type,
        evidence_id=evidence_id,
        communication_id=communication_id,
        provider=result.provider,
        model=result.model,
        prompt_version=prompt_version,
        is_mock=result.is_mock,
        status="SUCCEEDED",
        structured_result=result.output.model_dump(mode="json"),
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    db.add(analysis)
    db.flush()
    return analysis


def _record_failure(
    db: Session,
    complaint: Complaint,
    analysis_type: str,
    prompt_version: str,
    provider: AIProvider,
    error: AIProviderError,
    evidence_id: uuid.UUID | None = None,
    communication_id: uuid.UUID | None = None,
) -> None:
    """Record a failed AI call and show it on the timeline. The caller commits."""
    # Log for developers (no photo, no personal data, no secrets).
    logger.warning(
        "AI %s failed for complaint %s: %s (%s)", analysis_type, complaint.id, error.code, error
    )
    db.add(
        AIAnalysis(
            complaint_id=complaint.id,
            analysis_type=analysis_type,
            evidence_id=evidence_id,
            communication_id=communication_id,
            provider=provider.name,
            model=provider.model,
            prompt_version=prompt_version,
            is_mock=provider.is_mock,
            status="FAILED",
            error_code=error.code,
            error_message=str(error)[:500],
        )
    )
    complaint_service.record_event(
        db,
        complaint,
        EventType.AI_ANALYSIS_FAILED,
        _FAILURE_TEXT[analysis_type],
        actor=Actor.SYSTEM,
        details={"error_code": error.code},
    )


# ── Vision: photo → suggestions ─────────────────────────────────────────────


def analyze_photo(
    db: Session,
    storage: StorageService,
    provider: AIProvider,
    user: User,
    complaint_id: uuid.UUID,
    evidence_id: uuid.UUID | None,
) -> AIAnalysis:
    complaint = _editable_complaint(db, user, complaint_id)
    photos = [e for e in complaint.evidence if e.evidence_type == "ORIGINAL"]
    if evidence_id is not None:
        photo = next((e for e in photos if e.id == evidence_id), None)
        if photo is None:
            raise NotFoundError("Photo not found.")
    elif photos:
        photo = photos[0]
    else:
        raise BusinessRuleError("Add a photo before asking the AI to analyse it.")

    image = prepare_for_model(read_evidence_file(storage, photo))
    try:
        result = vision_agent.analyze_photo(provider, image)
    except AIProviderError as error:
        _record_failure(
            db, complaint, VISION, vision_agent.PROMPT_VERSION, provider, error, photo.id
        )
        db.commit()
        raise AIUnavailableError(_VISION_UNAVAILABLE, {"reason": error.code}) from error

    analysis = _record_success(db, complaint, VISION, vision_agent.PROMPT_VERSION, result, photo.id)
    output = result.output
    label = CATEGORY_LABELS[Category(output.category)]
    complaint_service.record_event(
        db,
        complaint,
        EventType.AI_ANALYSIS_COMPLETED,
        f"AI analysed the photo and suggested: {label}.",
        actor=Actor.AI,
        details={"analysis_id": str(analysis.id), "is_mock": result.is_mock},
    )
    db.commit()
    return analysis


def latest_photo_analysis(db: Session, user: User, complaint_id: uuid.UUID) -> AIAnalysis | None:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    return db.scalar(
        select(AIAnalysis)
        .where(
            AIAnalysis.complaint_id == complaint.id,
            AIAnalysis.analysis_type == VISION,
            AIAnalysis.status == "SUCCEEDED",
        )
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )


# ── Complaint letter ────────────────────────────────────────────────────────


def generate_complaint_draft(
    db: Session,
    provider: AIProvider,
    user: User,
    complaint_id: uuid.UUID,
    request: ComplaintDraftRequest,
) -> ComplaintDraftResponse:
    complaint = _editable_complaint(db, user, complaint_id)

    missing = [
        label
        for label, present in [
            ("a title", complaint.title),
            ("a description", complaint.description),
            ("the type of issue", complaint.category),
            ("a confirmed location", complaint.location_confirmed_at),
        ]
        if not present
    ]
    if missing:
        raise BusinessRuleError(f"Before writing the letter, add {', '.join(missing)}.")
    if complaint.draft_body and not request.replace_existing:
        raise ConflictError(
            "You already have a complaint letter. Confirm that you want to replace it."
        )

    facts = build_facts(complaint, user)
    analysis: AIAnalysis | None = None
    is_mock = False
    if request.mode == "ai":
        try:
            result = complaint_writer_agent.write_letter_prose(provider, facts)
        except AIProviderError as error:
            _record_failure(
                db,
                complaint,
                COMPLAINT_DRAFT,
                complaint_writer_agent.PROMPT_VERSION,
                provider,
                error,
            )
            db.commit()
            raise AIUnavailableError(_LETTER_UNAVAILABLE, {"reason": error.code}) from error
        analysis = _record_success(
            db, complaint, COMPLAINT_DRAFT, complaint_writer_agent.PROMPT_VERSION, result
        )
        prose = result.output
        is_mock = result.is_mock
    else:
        prose = template_prose(facts)

    subject, body = render_letter(prose, facts)
    complaint.draft_subject = subject[:200]
    complaint.draft_body = body
    complaint_service.withdraw_approval(db, complaint, "the letter was rewritten")
    complaint_service.record_event(
        db,
        complaint,
        EventType.COMPLAINT_DRAFT_GENERATED,
        "AI drafted the complaint letter."
        if request.mode == "ai"
        else "Complaint letter created from the standard template.",
        actor=Actor.AI if request.mode == "ai" else Actor.SYSTEM,
        details={"analysis_id": str(analysis.id) if analysis else None, "is_mock": is_mock},
    )
    db.commit()
    return ComplaintDraftResponse(
        draft_subject=complaint.draft_subject,
        draft_body=body,
        source=request.mode,
        is_mock=is_mock,
        analysis_id=analysis.id if analysis else None,
    )


# ── Monitoring: replies and reminders (called by monitoring/service.py) ─────


def classify_reply(
    db: Session, provider: AIProvider, complaint: Complaint, reply: Communication
) -> AIResult[ReplyClassification] | None:
    """The AI's reading of a reply, or None if the AI is unavailable (the citizen then decides).
    Never changes anything itself. The caller commits."""
    try:
        result = monitoring_agent.classify_reply(
            provider,
            subject=reply.subject,
            body=reply.body,
            own_reference=complaint.public_reference,
        )
    except AIProviderError as error:
        _record_failure(
            db,
            complaint,
            REPLY_CLASSIFICATION,
            monitoring_agent.CLASSIFY_PROMPT_VERSION,
            provider,
            error,
            communication_id=reply.id,
        )
        return None
    _record_success(
        db,
        complaint,
        REPLY_CLASSIFICATION,
        monitoring_agent.CLASSIFY_PROMPT_VERSION,
        result,
        communication_id=reply.id,
    )
    return result


def write_followup_prose(
    db: Session, provider: AIProvider, complaint: Complaint, facts: dict
) -> tuple[FollowupProse, bool]:
    """Wording for a reminder: from the AI, or the standard template if the AI fails.
    Returns (prose, is_mock). The caller commits."""
    try:
        result = monitoring_agent.write_followup_prose(provider, facts)
    except AIProviderError as error:
        _record_failure(
            db,
            complaint,
            FOLLOWUP_DRAFT,
            monitoring_agent.FOLLOWUP_PROMPT_VERSION,
            provider,
            error,
        )
        return template_followup_prose(facts), False
    _record_success(db, complaint, FOLLOWUP_DRAFT, monitoring_agent.FOLLOWUP_PROMPT_VERSION, result)
    return result.output, result.is_mock


# ── Resolution: before/after comparison (called by resolutions/service.py) ──


def compare_photos(
    db: Session,
    storage: StorageService,
    provider: AIProvider,
    complaint: Complaint,
    *,
    before: Evidence,
    after: Evidence,
) -> tuple[AIResult[ResolutionAssessment] | None, AIAnalysis | None, str | None]:
    """The AI's comparison of two photos, or (None, None, error_code) if the AI is unavailable
    or answered invalidly; the citizen then compares the photos alone. The caller commits."""
    images = (
        prepare_for_model(read_evidence_file(storage, before)),
        prepare_for_model(read_evidence_file(storage, after)),
    )
    try:
        result = resolution_agent.compare_photos(provider, *images)
    except AIProviderError as error:
        _record_failure(
            db, complaint, RESOLUTION, resolution_agent.PROMPT_VERSION, provider, error, after.id
        )
        return None, None, error.code
    analysis = _record_success(
        db, complaint, RESOLUTION, resolution_agent.PROMPT_VERSION, result, after.id
    )
    return result, analysis, None
