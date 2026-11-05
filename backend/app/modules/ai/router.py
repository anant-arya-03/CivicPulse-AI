import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.integrations.ai_providers.base import AIProvider
from app.integrations.ai_providers.factory import get_ai_provider
from app.integrations.storage.base import StorageService
from app.integrations.storage.factory import get_storage
from app.modules.ai import service
from app.modules.ai.schemas import (
    AnalysisRead,
    AnalyzeRequest,
    ComplaintDraftRequest,
    ComplaintDraftResponse,
    analysis_to_read,
)
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(prefix="/complaints/{complaint_id}", tags=["ai"])

Provider = Annotated[AIProvider, Depends(get_ai_provider)]
Storage = Annotated[StorageService, Depends(get_storage)]
# AI calls are slow and (with a real model) cost money, so they are rate-limited per client.
ai_rate_limit = Depends(RateLimit("ai", times=10, seconds=60))


@router.post(
    "/analysis",
    response_model=AnalysisRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ai_rate_limit],
)
def analyze_photo(
    complaint_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    storage: Storage,
    provider: Provider,
    data: AnalyzeRequest | None = None,
):
    evidence_id = data.evidence_id if data else None
    analysis = service.analyze_photo(db, storage, provider, user, complaint_id, evidence_id)
    return analysis_to_read(analysis)


@router.get("/analysis", response_model=AnalysisRead | None)
def latest_analysis(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """The latest successful photo analysis, or null if there isn't one yet."""
    analysis = service.latest_photo_analysis(db, user, complaint_id)
    return analysis_to_read(analysis) if analysis else None


@router.post(
    "/complaint-draft",
    response_model=ComplaintDraftResponse,
    dependencies=[ai_rate_limit],
)
def generate_complaint_draft(
    complaint_id: uuid.UUID,
    data: ComplaintDraftRequest,
    user: CurrentUser,
    db: DbSession,
    provider: Provider,
):
    return service.generate_complaint_draft(db, provider, user, complaint_id, data)
