import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.integrations.email_providers.base import EmailProvider
from app.integrations.email_providers.factory import get_email_provider
from app.modules.auth.dependencies import CurrentUser
from app.modules.communications import service
from app.modules.communications.schemas import (
    ApproveRequest,
    CommunicationRead,
    FollowupUpdate,
    SubmissionPreview,
)

router = APIRouter(tags=["communications"])

Provider = Annotated[EmailProvider, Depends(get_email_provider)]
submit_rate_limit = Depends(RateLimit("submit", times=10, seconds=60))


@router.get("/complaints/{complaint_id}/submission-preview", response_model=SubmissionPreview)
def submission_preview(
    complaint_id: uuid.UUID, user: CurrentUser, db: DbSession, provider: Provider
):
    return service.preview(db, provider, user, complaint_id)


@router.post(
    "/complaints/{complaint_id}/approve",
    response_model=CommunicationRead,
    dependencies=[submit_rate_limit],
)
def approve(
    complaint_id: uuid.UUID,
    data: ApproveRequest,
    user: CurrentUser,
    db: DbSession,
    provider: Provider,
):
    return service.approve(db, provider, user, complaint_id, data.content_sha256)


@router.post(
    "/communications/{communication_id}/send",
    response_model=CommunicationRead,
    dependencies=[submit_rate_limit],
)
def send(communication_id: uuid.UUID, user: CurrentUser, db: DbSession, provider: Provider):
    return service.send(db, provider, user, communication_id)


@router.get("/complaints/{complaint_id}/communications", response_model=list[CommunicationRead])
def list_communications(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return service.list_communications(db, user, complaint_id)


# ── Follow-up reminders (drafted by the worker, approved and sent by the citizen) ──


@router.patch("/communications/{communication_id}", response_model=CommunicationRead)
def update_followup(
    communication_id: uuid.UUID, data: FollowupUpdate, user: CurrentUser, db: DbSession
):
    return service.update_followup(db, user, communication_id, data)


@router.post(
    "/communications/{communication_id}/approve",
    response_model=CommunicationRead,
    dependencies=[submit_rate_limit],
)
def approve_followup(
    communication_id: uuid.UUID,
    data: ApproveRequest,
    user: CurrentUser,
    db: DbSession,
    provider: Provider,
):
    return service.approve_followup(db, provider, user, communication_id, data.content_sha256)


@router.post("/communications/{communication_id}/dismiss", response_model=CommunicationRead)
def dismiss_followup(communication_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return service.dismiss_followup(db, user, communication_id)
