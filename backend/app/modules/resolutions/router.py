import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.integrations.ai_providers.base import AIProvider
from app.integrations.ai_providers.factory import get_ai_provider
from app.integrations.email_providers.base import EmailProvider
from app.integrations.email_providers.factory import get_email_provider
from app.integrations.storage.base import StorageService
from app.integrations.storage.factory import get_storage
from app.modules.auth.dependencies import CurrentUser
from app.modules.complaints import service as complaint_service
from app.modules.complaints.schemas import ComplaintRead
from app.modules.resolutions import service
from app.modules.resolutions.schemas import (
    CreateReviewRequest,
    DecisionRequest,
    ReopenRequest,
    ResolutionReviewRead,
)

router = APIRouter(tags=["resolutions"])

AI = Annotated[AIProvider, Depends(get_ai_provider)]
Email = Annotated[EmailProvider, Depends(get_email_provider)]
Storage = Annotated[StorageService, Depends(get_storage)]
decision_rate_limit = Depends(RateLimit("decision", times=10, seconds=60))


@router.post(
    "/complaints/{complaint_id}/resolution-reviews",
    response_model=ResolutionReviewRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("ai", times=10, seconds=60))],
)
def create_review(
    complaint_id: uuid.UUID,
    data: CreateReviewRequest,
    user: CurrentUser,
    db: DbSession,
    storage: Storage,
    ai: AI,
):
    review = service.create_review(db, storage, ai, user, complaint_id, data.evidence_id)
    return service.to_read(db, review)


@router.get(
    "/complaints/{complaint_id}/resolution-reviews", response_model=list[ResolutionReviewRead]
)
def list_reviews(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return [service.to_read(db, r) for r in service.list_reviews(db, user, complaint_id)]


@router.post(
    "/resolution-reviews/{review_id}/decision",
    response_model=ResolutionReviewRead,
    dependencies=[decision_rate_limit],
)
def decide(
    review_id: uuid.UUID, data: DecisionRequest, user: CurrentUser, db: DbSession, email: Email
):
    review = service.decide(db, email, user, review_id, data.decision, data.notes)
    return service.to_read(db, review)


@router.post(
    "/complaints/{complaint_id}/reopen",
    response_model=ComplaintRead,
    dependencies=[decision_rate_limit],
)
def reopen(
    complaint_id: uuid.UUID, data: ReopenRequest, user: CurrentUser, db: DbSession, email: Email
):
    return complaint_service.to_read(service.reopen(db, email, user, complaint_id, data.notes))
